#!/bin/sh

# 
# Copyright 2010 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

#args:

HOME_HOST="$1"
SVCPREFIX="$2"
admin="$3"
uploader="$4"
downloader="$5"
curator="$6"
grader="$7"

echo args: "$@"

shift 7

# this script will recreate all tables, but only on a clean database

echo "create core tables..."

psql -q -t <<EOF
CREATE TABLE resources ( subject bigserial PRIMARY KEY );
CLUSTER resources USING resources_pkey;
CREATE SEQUENCE transmitnumber;
CREATE SEQUENCE keygenerator;
CREATE TABLE subjecttags ( subject bigint REFERENCES resources (subject) ON DELETE CASCADE, tagname text, UNIQUE (subject, tagname) );
CLUSTER subjecttags USING subjecttags_subject_key;
EOF

# pre-established stored data
# MUST NOT be called more than once with same name during deploy 
# e.g. only deploys version 1 properly
dataset_core()
{
   psql -A -t -q <<EOF
INSERT INTO resources DEFAULT VALUES RETURNING subject;
EOF
}

dataset_complete()
{
   # args: <subjectid> <name> url <url> <owner> [<readuser>]...
   # args: <subjectid> <name> blank <owner> [<readuser>]...
   # args: <subjectid> <name> typedef <owner> [<readuser>]...
   # args: <subjectid> <name> tagdef <owner> [<readuser>]...
   # args: <subjectid> <name> config <owner> [<readuser>]...
   # args: <subjectid> <name> view <owner> [<readuser>]...

   local subject="$1"
   local file="$2"
   local type="$3"
   local url
   local owner

   shift 3

   case "$type" in
      url|file)
         url="$1"
         shift         

         case "$url" in
            http*:*|/*)
               url="$url"
               ;;
            *)
               url="https://${HOME_HOST}/${SVCPREFIX}/query/$url"
              ;;
         esac
         ;;
      blank|typedef|tagdef|config|view)
         :
         ;;
      *)
         echo "Unsupported dataset format: $*" >&2
         exit 1
         ;;
   esac

   local owner="$1"
   shift

   if [[ -n "$owner" ]]
   then
       tag "$subject" owner text "$owner" >&2
   fi

   while [[ $# -gt 0 ]]
   do
      tag "$subject" "read users" text "$1" >&2
      shift
   done

   case "$type" in
      url|file)
	 tag "$subject" name text "$file" >&2
	 tag "$subject" 'latest with name' text "$file" >&2
	 tag "$subject" vname text "$file@1" >&2
	 tag "$subject" version int8 1 >&2

	 case "$type" in
	     url)
		 tag "$subject" url text "$url" >&2
		 ;;
	 esac
	 ;;
      config|view)
	 tag "$subject" "$type" text "$file" >&2
	 ;;
   esac
}

dataset()
{
    local subject=$(dataset_core)
    dataset_complete "$subject" "$@"
    echo "$subject"
}

tag()
{
   # args: file tag typestr [value]...
   # for non-empty typestr
   #     does one default value insert for 0 values
   #     does N value inserts for N>0 values

   local file="$1"
   local tagname="$2"
   local typestr="$3"
   local count
   shift 3

   echo "set /tags/$file/$tagname=" "$@"
   if [[ -z "$typestr" ]] || [[ $# -eq 0 ]]
   then
       count=$(psql -A -t -q <<EOF
SELECT count(*) FROM "_$tagname" WHERE subject = '$file';
EOF
       )
       if [[ $count -eq 0 ]]
	   then
	   psql -q -t <<EOF
INSERT INTO "_$tagname" ( subject ) VALUES ( '$file' );
EOF
       fi
   elif [[ $# -gt 0 ]]
   then
       while [[ $# -gt 0 ]]
	 do
	 count=$(psql -A -t -q <<EOF
SELECT count(*) FROM "_$tagname" WHERE subject = '$file' AND value = '$1';
EOF
	 )
	 if [[ $count -eq 0 ]]
	     then
	     psql -q -t <<EOF
INSERT INTO "_$tagname" ( subject, value ) VALUES ( '$file', '$1' );
EOF
	 fi
         shift
      done
   fi

   # add to filetags only if this insert changes status
   untracked=$(psql -A -t -q <<EOF
SELECT DISTINCT a.subject
FROM "_$tagname" AS a 
LEFT OUTER JOIN subjecttags AS b ON (a.subject = b.subject AND b.tagname = '$tagname')
WHERE b.subject IS NULL AND a.subject = '$file';
EOF
   )

   if [[ -n "$untracked" ]]
   then
      psql -q -t <<EOF
INSERT INTO subjecttags (subject, tagname) VALUES ('$file', '$tagname');
EOF
   fi

   updated=$(psql -A -q -t <<EOF
UPDATE "_subject last tagged" SET value = 'now' WHERE subject = '$file' RETURNING subject;
EOF
   )
   if [[ -z "$updated" ]]
   then
       psql -A -q -t <<EOF
INSERT INTO "_subject last tagged" (subject, value) VALUES ('$file', 'now');
EOF
   fi

   updated=$(psql -A -q -t <<EOF
UPDATE "_tag last modified" SET value = 'now' WHERE subject IN (SELECT subject FROM "_tagdef" WHERE value = '$tagname') RETURNING subject;
EOF
   )
   if [[ -z "$updated" ]]
   then
       psql -A -q -t <<EOF
INSERT INTO "_tag last modified" (subject, value) SELECT subject, 'now' FROM "_tagdef" WHERE value = '$tagname';
EOF
   fi

   updated=$(psql -A -q -t <<EOF
UPDATE "_subject last tagged txid" SET value = txid_current() WHERE subject = '$file' RETURNING subject;
EOF
   )
   if [[ -z "$updated" ]]
   then
       psql -A -q -t <<EOF
INSERT INTO "_subject last tagged txid" (subject, value) VALUES ('$file', txid_current());
EOF
   fi

   updated=$(psql -A -q -t <<EOF
UPDATE "_tag last modified txid" SET value = txid_current() WHERE subject IN (SELECT subject FROM "_tagdef" WHERE value = '$tagname') RETURNING subject;
EOF
   )
   if [[ -z "$updated" ]]
   then
       psql -A -q -t <<EOF
INSERT INTO "_tag last modified txid" (subject, value) SELECT subject, txid_current() FROM "_tagdef" WHERE value = '$tagname';
EOF
   fi

   
}

tagacl()
{
   # args: tagname {read|write} [value]...
   local tag=$(psql -A -t -q <<EOF
SELECT subject FROM "_tagdef" WHERE value = '$1';
EOF
   )
   local mode=$2
   shift 2
   while [[ $# -gt 0 ]]
   do
      tag "$tag" "tag $mode users" rolepat "$1"
      shift
   done
}

tagdef_phase2()
{
   # args: subject tagname dbtype owner readpolicy writepolicy multivalue [typestr [primarykey [tagref]]]

   # policy is one of:
   #   anonymous  -- any client can access
   #   subject  -- subject access rule is observed for tag access
   #   subjectowner  -- only subject owner can access
   #   tag -- tag access rule is observed for tag access
   #   tagorsubject -- tag or subject access rules are sufficient
   #   tagandsubject -- tag and subject access rules are required
   #   system  -- no client can access

   echo "populate tagdef '$2'..." >&2

   dataset_complete "$1" "" tagdef "$4" "*"
   local subject="$1"

   tag "$subject" "tagdef" text "$2" >&2
   tag "$subject" "tagdef active" >&2

   tag "$subject" "tagdef readpolicy" tagpolicy "$5" >&2
   tag "$subject" "tagdef writepolicy" tagpolicy "$6" >&2

   if [[ "$7" == "true" ]]
   then
      tag "$subject" "tagdef multivalue" >&2
   fi

   if [[ -n "$8" ]]
   then
      tag "$subject" "tagdef type" type "$8" >&2
   else
      tag "$subject" "tagdef type" type "$3" >&2
   fi

   if [[ "$9" == "true" ]]
   then
      tag "$subject" "tagdef unique" >&2
   fi
}

tagdef_phase1()
{
   # args: tagname dbtype owner readpolicy writepolicy multivalue [typestr [primarykey [tagref]]]

   local tagref
   local fk
   local default
   local uniqueval

   if [[ -n "$2" ]] && [[ "$2" != empty ]]
   then
      if [[ "$2" = "text" ]]
      then
         default="DEFAULT ''"
      else
         default=""
      fi

      if [[ "$1" = "vname" ]] || [[ "$8" = true ]]
      then
         fk="UNIQUE"
      else
         fk=""
      fi

      tagref="$9"

      if [[ -n "$tagref" ]]
      then
	  fk="${fk} REFERENCES \"_${tagref}\" (value) ON DELETE CASCADE"
      fi

      if [[ "$6" = "true" ]]
      then
         uniqueval='UNIQUE(subject, value)'
      else
         uniqueval='UNIQUE(subject)'
      fi

      # hack to use implicit indexes created by postgresql rather than creating redundant indexes
      # UNIQUE(subject, value) implies index _$1_subject_key on (subject, value)
      # UNIQUE(subject) implies index _$1_subject_key on (subject)

      psql -q -t >&2 <<EOF
CREATE TABLE "_$1" ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE, 
                       value $2 ${default} NOT NULL ${fk}, ${uniqueval} );
$(if [[ "$uniqueval" = "UNIQUE(subject)" ]] ; then 
     echo "CREATE INDEX \"_$1_subject_value_idx\" ON \"_$1\" (subject, value);" ;
     echo "CLUSTER \"_$1\" USING \"_$1_subject_value_idx\";" ;
  else 
     echo "CLUSTER \"_$1\" USING \"_$1_subject_key\";" ;
  fi)
EOF
   else
      psql -q -t >&2 <<EOF
CREATE TABLE "_$1" ( subject bigint UNIQUE NOT NULL REFERENCES resources (subject) ON DELETE CASCADE );
CLUSTER "_$1" USING "_$1_subject_key";
EOF
   fi

   local subject=$(dataset_core "" tagdef "$3" "*")
   
   echo "$subject"
}

tag_subjects=()
tag_names=()
tag_dbtypes=()
tag_owners=()
tag_readpolicies=()
tag_writepolicies=()
tag_multivalues=()
tag_typestrs=()

tagdef()
{
   tag_names[${#tag_names[*]}]="$1"
   tag_dbtypes[${#tag_dbtypes[*]}]="$2"
   tag_owners[${#tag_owners[*]}]="$3"
   tag_readpolicies[${#tag_readpolicies[*]}]="$4"
   tag_writepolicies[${#tag_writepolicies[*]}]="$5"
   tag_multivalues[${#tag_multivalues[*]}]="$6"
   tag_typestrs[${#tag_typestrs[*]}]="$7"
   tag_uniques[${#tag_uniques[*]}]="$8"
   tag_tagrefs[${#tag_tagrefs[*]}]="$9"
   tag_subjects[${#tag_subjects[*]}]=$(tagdef_phase1 "$@")
}

tagdefs_complete()
{
   local i
   echo ${!tag_names[*]}
   for i in ${!tag_names[*]}
   do
      tagdef_phase2 "${tag_subjects[$i]}" "${tag_names[$i]}" "${tag_dbtypes[$i]}" "${tag_owners[$i]}" "${tag_readpolicies[$i]}" "${tag_writepolicies[$i]}" "${tag_multivalues[$i]}" "${tag_typestrs[$i]}" "${tag_uniques[$i]}" "${tag_tagrefs[$i]}"
   done
}

typedef_core()
{
   typename="$1"
   dbtype="$2"
   desc="$3"
   tagref="$4"
   shift 3
   shift  # shift 4 can fail to shift when only 3 args were passed!
   local subject=$(dataset_core "" typedef "" "*")
   tag "$subject" "typedef" text "${typename}" >&2
   tag "$subject" "typedef dbtype" text "${dbtype}" >&2
   tag "$subject" "typedef description" text "${desc}" >&2
   if [[ $# -gt 0 ]]
   then
      tag "$subject" "typedef values" text "$@" >&2
   fi
   echo "$subject"
}

typedef_tagref()
{
    local subject="$1"
    local tagref="$2"
    dataset_complete "$subject" "" typedef "" "*"
    if [[ -n "$tagref" ]]
    then
	tag "$subject" "typedef tagref" text "$tagref" >&2
    fi
}

type_subjects=()
type_tagrefs=()

typedef()
{
    local subject=$(typedef_core "$@")
    type_subjects[${#type_subjects[*]}]="$subject"
    type_tagrefs[${#type_tagrefs[*]}]="$4"
}

typedefs_complete()
{
    local i
    for i in ${!type_subjects[*]}
    do
      typedef_tagref "${type_subjects[$i]}" "${type_tagrefs[$i]}"
    done
}

# sequencing is crucial here to avoid unresolved dependencies!

#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF
tagdef 'tagdef'              text        ""         anonymous   system       false      ""         true  
tagdef 'typedef'             text        ""         anonymous   subject      false      ""         true
tagdef 'typedef description' text        ""         anonymous   subject      false
tagdef 'typedef dbtype'      text        ""         anonymous   subject      false
tagdef 'typedef values'      text        ""         anonymous   subject      true
tagdef 'tagdef unique'       empty       ""         anonymous   system       false      ""
tagdef 'tagdef multivalue'   empty       ""         anonymous   system       false
tagdef 'tagdef active'       empty       ""         anonymous   system       false
tagdef 'tagdef readpolicy'   text        ""         anonymous   system       false      tagpolicy
tagdef 'tagdef writepolicy'  text        ""         anonymous   system       false      tagpolicy
tagdef 'id'                  int8        ""         anonymous   system       false      ""         true
tagdef 'config'              text        ""         anonymous   subject      false      ""         true
tagdef 'view'                text        ""         anonymous   subject      false      ""         true
tagdef 'tag read users'      text        ""         anonymous   subjectowner true       rolepat
tagdef 'tag write users'     text        ""         anonymous   subjectowner true       rolepat
tagdef owner                 text        ""         anonymous   tag          false      role
tagdef created               timestamptz ""         anonymous   system       false
tagdef "version created"     timestamptz ""         anonymous   system       false
tagdef "read users"          text        ""         anonymous   subjectowner true       rolepat
tagdef "write users"         text        ""         anonymous   subjectowner true       rolepat
tagdef "modified by"         text        ""         anonymous   system       false      role
tagdef modified              timestamptz ""         anonymous   system       false
tagdef "subject last tagged" timestamptz ""         anonymous   system       false
tagdef "tag last modified"   timestamptz ""         anonymous   system       false
tagdef "subject last tagged txid" int8   ""         anonymous   system       false
tagdef "tag last modified txid" int8     ""         anonymous   system       false
tagdef bytes                 int8        ""         anonymous   system       false
tagdef version               int8        ""         anonymous   system       false
tagdef name                  text        ""         anonymous   system       false
tagdef 'latest with name'    text        ""         anonymous   system       false      ""         true
tagdef vname                 text        ""         anonymous   system       false      ""         true
tagdef parentof              int8        ""         subject     subject      true       id
tagdef file                  text        ""         system      system       false      ""         true
tagdef url                   text        ""         subject     subject      false      url
tagdef content-type          text        ""         anonymous   subject      false
tagdef sha256sum             text        ""         anonymous   subject      false
tagdef key                   text        ""         anonymous   subject      false      ""         true
tagdef "check point offset"  int8        ""         anonymous   subject      false
tagdef "incomplete"          empty       ""         anonymous   subject      false
tagdef "list on homepage"    empty       "${admin}" anonymous   tag          false
tagdef "homepage order"      int8        "${admin}" anonymous   tag          false
tagdef "Image Set"           empty       "${admin}" subject     subject      false
tagdef 'tagdef type'         text        ""         anonymous   system       false      type       ""       typedef
tagdef 'typedef tagref'      text        ""         anonymous   subject      false      tagdef     ""       tagdef 
tagdef 'template mode'       text        "${admin}" anonymous   tag          false      'template mode'
tagdef 'template query'      text        "${admin}" subjectowner tag         true       ""
#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF

#       TYPENAME     DBTYPE        DESC                            TAGREF             ENUMs
typedef empty        ''            'No content'
typedef int8         int8          'Integer'
typedef float8       float8        'Floating point'
typedef date         date          'Date'
typedef timestamptz  timestamptz   'Date and time with timezone'
typedef text         text          'Text'
typedef role         text          'Role'
typedef rolepat      text          'Role pattern'
typedef dtype        text          'Dataset type'                  ""                 'blank Dataset node for metadata-only' 'file Named dataset for locally stored file' 'url Named dataset for URL redirecting'
typedef url          text          'URL'
typedef id           int8          'Subject ID or subquery'
typedef tagpolicy    text          'Tag policy model'              ""                 'anonymous Any client may access' 'subject Subject authorization is observed' 'subjectowner Subject owner may access' 'tag Tag authorization is observed' 'tagorsubject Tag or subject authorization is sufficient' 'tagandsubject Tag and subject authorization are required' 'system No client can access'
typedef type         text          'Scalar value type'             typedef
typedef tagdef       text          'Tag definition'                tagdef
typedef name         text          'Subject name'                  "latest with name"
typedef vname        text          'Subject name@version'          vname
typedef view         text          'View name'                     view
typedef 'template mode' text       'Template rendering mode'       ""                 'embedded Embedded in Tagfiler HTML' 'page Standalone document'
#       TYPENAME     DBTYPE        DESC                            TAGREF             ENUMs

# complete split-phase definitions and redefine as combined phase
tagdefs_complete
tagdef()
{
   local subject=$(tagdef_phase1 "$@")
   tagdef_phase2 "$subject" "$@"
}

typedefs_complete
typedef()
{
    local subject=$(typedef_core "$@")
    typedef_tagref "$subject" "$4"
}

#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF
tagdef 'default view'        text        ""         subject     subject      false      view       ""       view
tagdef contains              text        ""         subject     subject      true       name       ""       "latest with name"
tagdef vcontains             text        ""         subject     subject      true       vname      ""       vname
#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF


# add tagdef foreign key referencing constraint
# drop storage for psuedo tag 'id' which we can synthesize from any subject column
psql -e -t <<EOF
ALTER TABLE subjecttags ADD FOREIGN KEY (tagname) REFERENCES _tagdef (value) ON DELETE CASCADE;
DROP TABLE "_id";
CREATE FUNCTION 
  resources_authzinfo ( roles text[], ignore_read_authz boolean = False ) RETURNS TABLE ( subject int8, txid int8, owner text, readok boolean, writeok boolean ) AS \$\$
  SELECT r.subject AS subject, 
         t.value AS txid,
         o.value AS owner,
         bool_or(ru.value = ANY (\$1) OR o.value = ANY (\$1)) AS readok, 
         bool_or(wu.value = ANY (\$1) OR o.value = ANY (\$1)) AS writeok
  FROM resources r
  LEFT OUTER JOIN "_subject last tagged txid" t ON (r.subject = t.subject)
  LEFT OUTER JOIN "_owner" o ON (r.subject = o.subject)
  LEFT OUTER JOIN "_read users" ru ON (r.subject = ru.subject AND ru.value = ANY (\$1))
  LEFT OUTER JOIN "_write users" wu ON (r.subject = wu.subject AND wu.value = ANY (\$1))
  WHERE \$2 or o.value = ANY (\$1) OR ru.value IS NOT NULL
  GROUP BY r.subject, txid, o.value
\$\$ LANGUAGE SQL;
EOF

tagacl "list on homepage" read "*"
tagacl "list on homepage" write "${admin}"

tagacl "owner" write "${admin}"

tagacl "homepage order" read "*"
tagacl "homepage order" write "${admin}"


homepath="https://${HOME_HOST}/${SVCPREFIX}"

homelinks=(
$(dataset "Create catalog entries (expert mode)" url "${homepath}/file?action=define"              "${admin}")
$(dataset "Upload study"                         url "${homepath}/study?action=upload"             "${admin}" "${curator}" "${uploader}")
$(dataset "Download study"                       url "${homepath}/study?action=download"           "${admin}" "${curator}" "${downloader}")
$(dataset "Query by tags, latest versions"       url "${homepath}/query?action=edit&versions=latest"	"${admin}" "${curator}" "${downloader}")
$(dataset "Query by tags, all versions"          url "${homepath}/query?action=edit&versions=any"  "${admin}" "${curator}" "${downloader}")
$(dataset "View tag definitions"                 url "${homepath}/query/tagdef?view=tagdef"        "${admin}" "*")
$(dataset "Manage tag definitions (expert mode)" url "${homepath}/tagdef"                          "${admin}")
$(dataset "Manage roles"                         url "https://${HOME_HOST}/webauthn/role"          "${admin}")
)

i=0
while [[ $i -lt "${#homelinks[*]}" ]]
do
   tag "${homelinks[$i]}" "list on homepage"
   tag "${homelinks[$i]}" "homepage order" int8 "$(( $i + 100 ))"
   i=$(( $i + 1 ))
done

tagfilercfg=$(dataset "tagfiler" config "${admin}" "*")
tag "$tagfilercfg" "view" text "default"  # config="tagfiler" is also view="default"


cfgtags=$(dataset "config" view "${admin}" "*")

cfgtagdef()
{
   local tagname="_cfg_$1"
   shift
   tagdef "$tagname" "$@"
   tag "$cfgtags" "_cfg_file list tags" tagdef "$tagname"
   [[ "$tagname" == "_cfg_file list tags" ]] ||  tag "$cfgtags" "_cfg_tag list tags" tagdef "$tagname"
}

#      TAGNAME                        TYPE  OWNER   READPOL     WRITEPOL   MULTIVAL      TYPESTR    PKEY

# file list tags MUST BE DEFINED FIRST
cfgtagdef 'file list tags'            text  ""      subject     subject       true       tagdef
# tag list tags MUST BE DEFINED NEXT...
cfgtagdef 'tag list tags'             text  ""      subject     subject       true       tagdef

# THEN, need to do this manually to break dependency loop
tag "$cfgtags" "_cfg_tag list tags" tagname "_cfg_file list tags"

cfgtagdef 'file list tags write'      text  ""      subject     subject       true       tagdef
cfgtagdef 'tagdef write users'        text  ""      subject     subject       true       rolepat
cfgtagdef 'file write users'          text  ""      subject     subject       true       rolepat
cfgtagdef home                        text  ""      subject     subject       false
cfgtagdef 'webauthn home'             text  ""      subject     subject       false
cfgtagdef 'webauthn require'          empty ""      subject     subject       false
cfgtagdef 'store path'                text  ""      subject     subject       false
cfgtagdef 'log path'                  text  ""      subject     subject       false
cfgtagdef 'template path'             text  ""      subject     subject       false
cfgtagdef 'chunk bytes'               int8  ""      subject     subject       false
cfgtagdef 'policy remappings'         text  ""      subject     subject       true
cfgtagdef subtitle                    text  ""      subject     subject       false
cfgtagdef logo                        text  ""      subject     subject       false
cfgtagdef contact                     text  ""      subject     subject       false
cfgtagdef help                        text  ""      subject     subject       false
cfgtagdef bugs                        text  ""      subject     subject       false
cfgtagdef 'client connections'        int8  ""      subject     subject       false
cfgtagdef 'client upload chunks'      empty ""      subject     subject       false
cfgtagdef 'client download chunks'    empty ""      subject     subject       false
cfgtagdef 'client socket buffer size' int8  ""      subject     subject       false
cfgtagdef 'client retry count'        int8  ""      subject     subject       false
cfgtagdef 'client chunk bytes'        int8  ""      subject     subject       false
cfgtagdef 'client socket timeout'     int8  ""      subject     subject       false
cfgtagdef 'applet tags'               text  ""      subject     subject       true       tagdef
cfgtagdef 'applet tags require'       text  ""      subject     subject       true       tagdef
cfgtagdef 'applet custom properties'  text  ""      subject     subject       true
cfgtagdef 'applet test log'           text  ""      subject     subject       false
cfgtagdef 'applet test properties'    text  ""      subject     subject       true

#      TAGNAME                        TYPE  OWNER   READPOL     WRITEPOL   MULTIVAL      TYPESTR    PKEY

cfgtag()
{
   tagname="_cfg_$1"
   shift
   tag "$tagfilercfg" "$tagname" "$@"
}

#cfgtag "home" text 'https://${HOME_HOST}'
cfgtag "webauthn home" text "https://${HOME_HOST}/webauthn"
cfgtag "webauthn require"

#cfgtag "store path" text '${DATADIR}'
#cfgtag "log path" text '${LOGDIR}'
#cfgtag "template path" text '${TAGFILERDIR}/templates'
cfgtag "chunk bytes" text '1048576'

cfgtag "client connections" int8 '4'
cfgtag "client upload chunks"
cfgtag "client download chunks"
cfgtag "client socket buffer size" int8 '8192'
cfgtag "client retry count" int8 '10'
cfgtag "client chunk bytes" int8 '8388608'
cfgtag "client socket timeout" int8 '120'

cfgtag "file write users" text "*" "admin"
cfgtag "tagdef write users" text "*" "admin"

cfgtag "file list tags" text bytes owner 'read users' 'write users'
#cfgtag "file list tags write" text 'read users' 'write users' 'owner'

#cfgtag "applet tags" text ...
#cfgtag "applet tags require" text ...
#cfgtag "applet properties" text 'tagfiler.properties'

tagdeftags=$(dataset "tagdef" view "${admin}" "*")
for tagname in "tagdef type" "tagdef multivalue" "tagdef unique" "tagdef readpolicy" "tagdef writepolicy" "tag read users" "tag write users" "read users" "write users" "owner"
do
   tag "$tagdeftags" "_cfg_file list tags" tagdef "$tagname"
   tag "$tagdeftags" "_cfg_tag list tags" tagdef "$tagname"
done

typedeftags=$(dataset "typedef" view "${admin}" "*")
for tagname in "typedef description" "typedef dbtype" "typedef values" "typedef tagref"
do
   tag "$typedeftags" "_cfg_file list tags" tagdef "$tagname"
   tag "$typedeftags" "_cfg_tag list tags" tagdef "$tagname"
done

viewtags=$(dataset "view" view "${admin}" "*")
for tagname in "_cfg_file list tags" "_cfg_file list tags write" "_cfg_tag list tags"
do
   tag "$viewtags" "_cfg_file list tags" tagdef "$tagname"
   tag "$viewtags" "_cfg_tag list tags" tagdef "$tagname"
done

vcontainstags=$(dataset "vcontains" view "${admin}" "*")
for tagname in "vcontains"
do
   tag "$vcontainstags" "_cfg_file list tags" tagdef "$tagname"
   tag "$vcontainstags" "_cfg_tag list tags" tagdef "$tagname"
done

containstags=$(dataset "contains" view "${admin}" "*")
for tagname in "contains"
do
   tag "$containstags" "_cfg_file list tags" tagdef "$tagname"
   tag "$containstags" "_cfg_tag list tags" tagdef "$tagname"
done

urltags=$(dataset "url" view "${admin}" "*")
for tagname in "url"
do
   tag "$urltags" "_cfg_file list tags" tagdef "$tagname"
   tag "$urltags" "_cfg_tag list tags" tagdef "$tagname"
done

# remapping rules:
#  srcrole ; dstrole ; reader, ... ; writer, ...
# semi-colons required but readers and writers optional, e.g. srcrole;dstrole;;

# these are actual (not logical) role names just like other ACLs and metadata
# only the python code itself uses logical roles for built-in policies

writers=
readers=
readok=
writeok=
if [[ "${uploader}" = "${curator}" ]]
then
    # all uploaders are curators, so they retain access
    :
else
    # allow non-curator uploaders to retain access, without sharing with other non-curator uploaders
    readok=true
    writeok=true
fi

if [[ "${downloader}" = "${curator}" ]]
then
    # all downloaders are curators, so they retain access
    :
else
    # also give read access to all downloaders
    readers="${downloader}"
fi

cfgtag "policy remappings" text "${uploader};${curator};${readers};${writers};${readok};${writeok}"

#cfgtag "applet test properties" text '/home/userid/appletTest.properties'
#cfgtag "applet test log" text '/home/userid/applet.log'

cfgtag "subtitle" text "Tagfiler (trunk) on ${HOME_HOST}"
cfgtag "logo" text '<img alt="tagfiler" title="Tagfiler (trunk)" src="/'"${SVCPREFIX}"'/static/logo.png" width="245" height="167" />'
cfgtag "contact" text '<p>Your HTML here</p>'
cfgtag "help" text 'https://confluence.misd.isi.edu:8443/display/DEIIMGUP/Home'
cfgtag "bugs" text 'https://jira.misd.isi.edu/browse/DEIIMGUP'


cmddir=$(dirname "$0")
#. ./dbsetup-nei-demo.sh

#. ${cmddir}/dbsetup-psoc-demo.sh

while [ "$1" ]
do
	. ${cmddir}/dbsetup-$1-demo.sh
	shift 1
done
