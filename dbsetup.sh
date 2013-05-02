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

# this is installed to /usr/local/bin
tagfiler-webauthn2-deploy.py

# start a coprocess so we can coroutine with a single transaction
coproc { psql -q -t -A  ; } 

echo "create core tables..."

json_native_func()
{
    cat <<EOF
CREATE FUNCTION val2json($1) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' ELSE CAST(\$1 AS text) END ;
\$\$ LANGUAGE SQL;
EOF
}

json_munge_func()
{
    cat <<EOF
CREATE FUNCTION val2json($1) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' ELSE val2json( CAST(\$1 AS text) ) END ;
\$\$ LANGUAGE SQL;
EOF
}

get_index_name()
{
    # uses coroutined psql directly!

    # get_index_name tablename indexspec
    # e.g. get_index_name '_tagdef' 'subject, value'

    cat >&${COPROC[1]} <<EOF
SELECT count(*) FROM pg_catalog.pg_indexes
WHERE tablename = '$1'
  AND indexdef ~ '[(]$2( text_pattern_ops)?[)]' ;
EOF
    read -u ${COPROC[0]} count

    if [[ $count -ge 1 ]]
    then
	cat >&${COPROC[1]} <<EOF
SELECT indexname FROM pg_catalog.pg_indexes
WHERE tablename = '$1'
  AND indexdef ~ '[(]$2( text_pattern_ops)?[)]'
LIMIT 1 ;
EOF
	read -u ${COPROC[0]} indexname
	printf "%s\n" "$indexname"
    fi
}

cat >&${COPROC[1]} <<EOF
\\set ON_ERROR_STOP

BEGIN;

CREATE FUNCTION val2json(text) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' ELSE '"' || regexp_replace(\$1, '"', E'\\\\"', 'g') || '"' END ;
\$\$ LANGUAGE SQL;

CREATE FUNCTION val2json(boolean) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' WHEN \$1 THEN 'true' ELSE 'false' END ;
\$\$ LANGUAGE SQL;

$(json_native_func int)
$(json_native_func bigint)
$(json_native_func float8)
$(json_munge_func date)
$(json_munge_func timestamptz)

CREATE FUNCTION val2json(anyarray) RETURNS text AS \$\$
  SELECT 
    CASE WHEN \$1 IS NULL 
      THEN 'null' 
    ELSE '[' || array_to_string( (SELECT array_agg(val2json(v)) FROM (SELECT unnest(\$1) AS v) s), ',' ) || ']' 
    END ;
\$\$ LANGUAGE SQL;

CREATE FUNCTION jsonfield(text, text) RETURNS text AS \$\$
  SELECT val2json(\$1) || ':' || \$2 ;
\$\$ LANGUAGE SQL;

CREATE FUNCTION jsonobj(text[]) RETURNS text AS \$\$
  SELECT '{' || array_to_string(\$1, ',') || '}' ;
\$\$ LANGUAGE SQL;

CREATE TABLE resources ( subject bigserial PRIMARY KEY );
CREATE SEQUENCE transmitnumber;
CREATE SEQUENCE keygenerator;
EOF

resources_index=$(get_index_name 'resources' 'subject')

cat >&${COPROC[1]} <<EOF
CLUSTER resources USING "${resources_index}" ;
EOF


# pre-established stored data
# MUST NOT be called more than once with same name during deploy 
db_resources=( 0 )
last_subject=0
dataset_core()
{
    last_subject=$(( ${last_subject} + 1 ))
    cat >&${COPROC[1]} <<EOF
INSERT INTO resources (subject) VALUES (${last_subject});
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
   local onclick
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
      onclick)
         onclick="$1"
         shift   
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
      url|file|onclick)
	 tag "$subject" name text "$file" >&2

	 case "$type" in
	     url)
		 tag "$subject" url text "$url" >&2
		 ;;
	     onclick)
		 tag "$subject" onclick text "$onclick" >&2
		 ;;
	 esac
	 ;;
      config|view)
	 tag "$subject" "$type" text "$file" >&2
	 ;;
   esac

   insert_or_update $subject "subject last tagged" "'now'"
   insert_or_update $subject "subject last tagged txid" "txid_current()"
}

dataset()
{
    dataset_core
    local subject=${last_subject}
    dataset_complete "$subject" "$@"
}

insert_or_update()
{
    # args: subject tagname 'value' (caller quotes value as necessary)
    cat >&${COPROC[1]} <<EOF
SELECT count(*) FROM "_$2" WHERE subject = $1;
EOF
    read -u ${COPROC[0]} count

    if [[ $count -eq 0 ]]
    then
	cat >&${COPROC[1]} <<EOF
INSERT INTO "_$2" (subject, value) VALUES ($1, $3);
EOF
    else
	cat >&${COPROC[1]} <<EOF
UPDATE "_$2" SET value = $3 WHERE subject = $1;
EOF
    fi

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
       cat >&${COPROC[1]}  <<EOF
SELECT count(*) FROM "_$tagname" WHERE subject = '$file';
EOF
       read -u ${COPROC[0]} count

       if [[ $count -eq 0 ]]
       then
	   cat >&${COPROC[1]} <<EOF
INSERT INTO "_$tagname" ( subject ) VALUES ( '$file' );
EOF
       fi
   elif [[ $# -gt 0 ]]
   then
       while [[ $# -gt 0 ]]
	 do
	 cat >&${COPROC[1]} <<EOF
SELECT count(*) FROM "_$tagname" WHERE subject = '$file' AND value = '$1';
EOF
	 read -u ${COPROC[0]} count

	 if [[ $count -eq 0 ]]
	 then
	     cat >&${COPROC[1]} <<EOF
INSERT INTO "_$tagname" ( subject, value ) VALUES ( '$file', '$1' );
EOF
	 fi
         shift
      done
   fi

}

tagacl()
{
   # args: tagname {read|write} [value]...
   local tag
   cat >&${COPROC[1]} <<EOF
SELECT subject FROM "_tagdef" WHERE value = '$1';
EOF
   read -u ${COPROC[0]} tag
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
   #   tagorowner -- tag or ownership is sufficient
   #   tagandowner -- tag and ownership are required
   #   system  -- no client can access

   echo "populate tagdef '$2'..." >&2

   dataset_complete "$1" "" tagdef "$4" "*"
   local subject="$1"

   tag "$subject" "tagdef" text "$2" >&2
   tag "$subject" "tagdef active" boolean true >&2

   tag "$subject" "tagdef readpolicy" tagpolicy "$5" >&2
   tag "$subject" "tagdef writepolicy" tagpolicy "$6" >&2

   if [[ "$7" == "true" ]]
   then
      tag "$subject" "tagdef multivalue" boolean true >&2
   else
      tag "$subject" "tagdef multivalue" boolean false >&2
   fi

   if [[ -n "$8" ]]
   then
      tag "$subject" "tagdef type" type "$8" >&2
   else
      tag "$subject" "tagdef type" type "$3" >&2
   fi

   if [[ "$9" == "true" ]]
   then
      tag "$subject" "tagdef unique" boolean true >&2
   else
      tag "$subject" "tagdef unique" boolean false >&2
   fi

   insert_or_update $subject "tag last modified" "'now'"
   insert_or_update $subject "tag last modified txid" "txid_current()"
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
      opclass=''
      if [[ "$2" = "text" ]]
      then
         default="DEFAULT ''"
	 opclass="text_pattern_ops"
      elif [[ "$2" = "boolean" ]]
      then
	 default="DEFAULT False"
      else
         default=""
      fi

      if [[ "$8" = true ]]
      then
         fk="UNIQUE"
      else
         fk=""
      fi

      tagref="$9"

      if [[ -n "$tagref" ]] && [[ "$tagref" != 'id' ]]
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

      cat >&${COPROC[1]} <<EOF
CREATE TABLE "_$1" ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE, 
                       value $2 ${default} NOT NULL ${fk}, ${uniqueval} );
CREATE INDEX "_$1_value_idx" ON "_$1" (value ${opclass}) ;
EOF
      if [[ "$6" = "true" ]]
      then
	  indexspec="subject, value"
      else
	  indexspec="subject"
      fi
   else
      cat >&${COPROC[1]} <<EOF
CREATE TABLE "_$1" ( subject bigint UNIQUE NOT NULL REFERENCES resources (subject) ON DELETE CASCADE );
EOF
      indexspec="subject"
   fi

   tagdef_cluster_index=$(get_index_name "_$1" "$indexspec")

   cat >&${COPROC[1]} <<EOF
CLUSTER "_$1" USING "${tagdef_cluster_index}" ;
EOF

   dataset_core "" tagdef "$3" "*"
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
   tagdef_phase1 "$@"
   tag_subjects[${#tag_subjects[*]}]=${last_subject}
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
   dataset_core "" typedef "" "*"
   local subject=${last_subject}
   tag "$subject" "typedef" text "${typename}" >&2
   tag "$subject" "typedef dbtype" text "${dbtype}" >&2
   tag "$subject" "typedef description" text "${desc}" >&2
   if [[ $# -gt 0 ]]
   then
      tag "$subject" "typedef values" text "$@" >&2
   fi
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
    typedef_core "$@"
    local subject=${last_subject}
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
tagdef 'tagdef unique'       boolean       ""         anonymous   system       false      ""
tagdef 'tagdef multivalue'   boolean       ""         anonymous   system       false
tagdef 'tagdef active'       boolean       ""         anonymous   system       false
tagdef 'tagdef readpolicy'   text        ""         anonymous   system       false      tagpolicy
tagdef 'tagdef writepolicy'  text        ""         anonymous   system       false      tagpolicy
tagdef 'id'                  int8        ""         anonymous   system       false      ""         true
tagdef 'readok'              boolean     ""         anonymous   system       false      ""
tagdef 'writeok'             boolean     ""         anonymous   system       false      ""
tagdef 'tags present'        text        ""         anonymous   system       true       tagdef     false     tagdef
tagdef 'config'              text        ""         anonymous   subject      false      ""         true
tagdef 'view'                text        ""         anonymous   subject      false      ""         true
tagdef 'tag read users'      text        ""         anonymous   subjectowner true       rolepat
tagdef 'tag write users'     text        ""         anonymous   subjectowner true       rolepat
tagdef owner                 text        ""         anonymous   tagorowner   false      role
tagdef created               timestamptz ""         anonymous   system       false
tagdef "read users"          text        ""         anonymous   subjectowner true       rolepat
tagdef "write users"         text        ""         anonymous   subjectowner true       rolepat
tagdef "modified by"         text        ""         anonymous   system       false      role
tagdef modified              timestamptz ""         anonymous   system       false
tagdef "subject last tagged" timestamptz ""         anonymous   system       false
tagdef "tag last modified"   timestamptz ""         anonymous   system       false
tagdef "subject last tagged txid" int8   ""         anonymous   system       false
tagdef "tag last modified txid" int8     ""         anonymous   system       false
tagdef bytes                 int8        ""         anonymous   system       false
tagdef name                  text        ""         anonymous   subjectowner false
tagdef file                  text        ""         system      system       false      ""         true
tagdef url                   text        ""         subject     subject      false      url
tagdef onclick               text        ""         anonymous   system       false
tagdef content-type          text        ""         anonymous   subject      false
tagdef sha256sum             text        ""         anonymous   subject      false
tagdef key                   text        ""         anonymous   subject      false      ""         true
tagdef "incomplete"          empty       ""         anonymous   subject      false
tagdef "list on homepage"    empty       "${admin}" anonymous   tag          false
tagdef "homepage order"      int8        "${admin}" anonymous   tag          false
tagdef 'tagdef type'         text        ""         anonymous   system       false      type       ""       typedef
tagdef 'typedef tagref'      text        ""         anonymous   subject      false      tagdef     ""       tagdef 
tagdef 'config binding'      int8        ""         subject     subject      true       id         ""       id
tagdef 'config parameter'    text        ""         subject     subject      false
tagdef 'config value'        text        ""         subject     subject      true
#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF

#       TYPENAME     DBTYPE        DESC                            TAGREF             ENUMs
typedef empty        ''            'No content'
typedef boolean      boolean       'Boolean (true or false)'       ''                 'True True' 'False False'
typedef int8         int8          'Integer'
typedef float8       float8        'Floating point'
typedef date         date          'Date (yyyy-mm-dd)'
typedef timestamptz  timestamptz   'Date and time with timezone'
typedef text         text          'Text'
typedef role         text          'Role'
typedef rolepat      text          'Role pattern'
typedef url          text          'URL'
typedef onclick      text          'Javascript function'
typedef id           int8          'Subject ID or subquery'
typedef tagpolicy    text          'Tag policy model'              ""                 'anonymous Any client may access' 'subject Subject authorization is observed' 'subjectowner Subject owner may access' 'tag Tag authorization is observed' 'tagorsubject Tag or subject authorization is sufficient' 'tagandsubject Tag and subject authorization are required' 'system No client can access'
typedef type         text          'Scalar value type'             typedef
typedef tagdef       text          'Tag definition'                tagdef
typedef view         text          'View name'                     view
typedef 'GUI features' text       'GUI configuration mode'       ""                 'bulk_value_edit bulk value editing' 'bulk_subject_delete bulk subject delete' 'cell_value_edit cell-based value editing' 'file_download per-row file download' 'subject_delete per-row subject delete' 'view_tags per-row tag page' 'view_URL per-row view URL'
#       TYPENAME     DBTYPE        DESC                            TAGREF             ENUMs

# complete split-phase definitions and redefine as combined phase
tagdefs_complete
tagdef()
{
    tagdef_phase1 "$@"
    local subject=${last_subject}
    tagdef_phase2 "$subject" "$@"
    tag_names[${#tag_names[*]}]="$1"
}

typedefs_complete
typedef()
{
    typedef_core "$@"
    local subject=${last_subject}
    typedef_tagref "$subject" "$4"
}

#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF
tagdef 'default view'        text        ""         subject     subject      false      view       ""       view
tagdef 'view tags'           text        ""         subject     subject      true       tagdef     ""       tagdef
#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF


# drop storage for psuedo tag 'id' which we can synthesize from any subject column
cat >&${COPROC[1]} <<EOF
DROP TABLE "_id";
DROP TABLE "_readok";
DROP TABLE "_writeok";
EOF

tagacl "list on homepage" read "*"
tagacl "list on homepage" write "${admin}"

tagacl "owner" write "${admin}"

tagacl "homepage order" read "*"
tagacl "homepage order" write "${admin}"


homepath="https://${HOME_HOST}/${SVCPREFIX}"

homelink_pos=0
homelink()
{
    dataset "$@"
    tag ${last_subject} "list on homepage"
    tag ${last_subject} "homepage order" int8 "$(( ${homelink_pos} + 100 ))"
    homelink_pos=$(( ${homelink_pos} + 1 ))
}

homelink "Query by tags"                        onclick "${homepath}/query"                           "${admin}" "${curator}" "${downloader}"
#homelink "Create catalog entries (expert mode)" url "${homepath}/file?action=define"              "${admin}"
homelink "View tag definitions"                 onclick "${homepath}/query/tagdef?view=tagdef"        "${admin}" "*"
homelink "View type definitions"                onclick "${homepath}/query/typedef?view=typedef"      "${admin}" "*"
homelink "View view definitions"                onclick "${homepath}/query/view?view=view"            "${admin}" "*"
#homelink "Manage tag definitions (expert mode)" onclick "${homepath}/tagdef"                          "${admin}"
homelink "Manage catalog configuration"         onclick "${homepath}/query/config=tagfiler(config%20binding)/?view=config"            "${admin}"

#homelink "Query by tags"                        onclick "javascript:queryByTags()"                           "${admin}" "${curator}" "${downloader}"
homelink "Create catalog entries (expert mode)" onclick "javascript:createCustomDataset()"              "${admin}" "*"
#homelink "View tag definitions"                 onclick "javascript:viewLink(\"tagdef?view=tagdef\")"        "${admin}" "*"
#homelink "View type definitions"                onclick "javascript:viewLink(\"typedef?view=typedef\")"      "${admin}" "*"
#homelink "View view definitions"                onclick "javascript:viewLink(\"view?view=view\")"            "${admin}" "*"
homelink "Manage tag definitions (expert mode)" onclick "javascript:manageAvailableTagDefinitions()"                          "${admin}"
#homelink "Manage catalog configuration"         onclick "javascript:getTagDefinition(\"tags/config=tagfiler\", null)"            "${admin}"

#dataset "Manage roles"                         url "https://${HOME_HOST}/webauthn/role"          "${admin}"

dataset "tagfiler" config "${admin}" "*"
tagfilercfg=${last_subject}


#      TAGNAME                        TYPE  OWNER   READPOL     WRITEPOL   MULTIVAL      TYPESTR    PKEY  TAGREF

#tag "file list tags write" text 'read users' 'write users' 'owner'

cfgtag()
{
    local binding

    dataset "" blank "${admin}" "*"
    binding=${last_subject}

    tag "$tagfilercfg" "config binding" int8 "$binding"

    tag "$binding" "config parameter" text "$1"
    shift
    tag "$binding" "config value" "$@"
}

cfgtag "chunk bytes" text '1048576'
cfgtag "file write users" text "*" "admin"
cfgtag "tagdef write users" text "*" "admin"
cfgtag "policy remappings" text "${uploader};${curator};${readers};${writers};${readok};${writeok}"
cfgtag "subtitle" text "Tagfiler (trunk) on ${HOME_HOST}"
cfgtag "logo" text '<img alt="tagfiler" title="Tagfiler (trunk)" src="/'"${SVCPREFIX}"'/static/logo.png" width="245" height="167" />'
cfgtag "help" text 'https://confluence.misd.isi.edu:8443/display/~karlcz/Tagfiler'
cfgtag "bugs" text 'https://jira.misd.isi.edu/browse/PSOC'
cfgtag "enabled GUI features" text 'bulk_value_edit' 'bulk_subject_delete' 'cell_value_edit' 'file_download' 'subject_delete' 'view_tags' 'view_URL'

viewdef()
{
    local viewname="$1"
    shift

    dataset "$viewname" view "${admin}" "*"
    local viewsubj
    viewsubj=${last_subject}

    [[ "$#" -gt 0 ]] && tag "$viewsubj" "view tags" tagdef "$@"
}

viewdef default 'id' 'name' bytes owner 'read users' 'write users' "subject last tagged"
viewdef config 'config parameter' 'config value'
viewdef tagdef 'tagdef' "tagdef type" "tagdef multivalue" "tagdef unique" "tagdef readpolicy" "tagdef writepolicy" "tag read users" "tag write users" "read users" "write users" "owner"
viewdef typedef 'id' 'typedef' "typedef description" "typedef dbtype" "typedef values" "typedef tagref"
viewdef view 'view' "view tags" "read users" "write users" "owner"
viewdef alltags

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


cat >&${COPROC[1]} <<EOF
INSERT INTO "_tags present" (subject, value)
  SELECT 0, '' WHERE False
  $(for tagname in "${tag_names[@]}"
    do
        if [[ "$tagname" != 'id' ]] && [[ "$tagname" != 'readok' ]] && [[ "$tagname" != 'writeok' ]] && [[ "$tagname" != 'tags present' ]]
        then
           cat <<EOF2
  UNION SELECT DISTINCT subject, '${tagname}' FROM "_${tagname}"
  UNION SELECT subject, 'id' FROM resources
  UNION SELECT subject, 'readok' FROM resources
  UNION SELECT subject, 'writeok' FROM resources
  UNION SELECT subject, 'tags present' FROM resources
EOF2
        fi
    done)
;

SELECT setval('resources_subject_seq', $(( ${last_subject} + 1 )));

COMMIT ;

\q

EOF

: {COPROC[1]}>&-
wait ${COPROC_PID}

cmddir=$(dirname "$0")
#. ./dbsetup-nei-demo.sh

#. ${cmddir}/dbsetup-psoc-demo.sh

while [ "$1" ]
do
	. ${cmddir}/dbsetup-$1-demo.sh
	shift 1
done
