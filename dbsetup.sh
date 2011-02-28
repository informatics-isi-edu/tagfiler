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

# this script will recreate all tables, but only on a clean database

echo "create core tables..."

psql -q -t <<EOF
CREATE TABLE resources ( subject bigserial PRIMARY KEY );
CREATE SEQUENCE transmitnumber;
CREATE SEQUENCE keygenerator;
EOF

# insert/get normalized datum id
dim_datum_id()
{
    # args: dimtype datum
    local id=$(psql -A -t -q <<EOF
SELECT id FROM "dim_${1}" WHERE "dim_${1}".value = '$2';
EOF
    )

    if [[ -z "$id" ]]
    then
	id=$(psql -A -t -q <<EOF
INSERT INTO "dim_${1}" (value) VALUES ($datum) RETURNING id;
EOF
	)
    fi

    echo "$id"
}

# pre-established stored data
# MUST NOT be called more than once with same name during deploy 
# e.g. only deploys version 1 properly
dataset()
{
   # args: <name> url <url> <owner> [<readuser>]...
   # args: <name> blank <owner> [<readuser>]...
   # args: <name> typedef <owner> [<readuser>]...
   # args: <name> tagdef <owner> [<readuser>]...
   # args: <name> config <owner> [<readuser>]...
   # args: <name> view <owner> [<readuser>]...

   local file="$1"
   local type="$2"
   local url
   local owner

   shift 2

   case "$type" in
      url)
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

   local subject=$(psql -A -t -q <<EOF
INSERT INTO resources DEFAULT VALUES RETURNING subject;
EOF
   )

   tag "$subject" dtype text "$type" >&2

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
      file|url)
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
   shift 3

   echo "set /tags/$file/$tagname=" "$@"
   if [[ -z "$typestr" ]] || [[ $# -eq 0 ]]
   then
      cat <<EOF
INSERT INTO "_$tagname" ( subject ) VALUES ( '$file' );
EOF
   elif [[ $# -gt 0 ]]
   then
      while [[ $# -gt 0 ]]
      do
	cat <<EOF
INSERT INTO "_$tagname" ( subject, value ) VALUES ( '$file', '$1' );
EOF
         shift
      done
   fi | psql -q -t

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

tagdef_tags()
{
   # args: tagname dbtype owner readpolicy writepolicy multivalue [typestr [primarykey]]

   # policy is one of:
   #   anonymous  -- any client can access
   #   users  -- any authenticated user can access
   #   file  -- file access rule is observed for tag access
   #   fowner  -- only file owner can access
   #   tag -- tag access rule is observed for tag access
   #   system  -- no client can access

   echo "create tagdef '$1'..." >&2

   local subject=$(dataset "" tagdef "$3" "*")

   tag "$subject" "tagdef" text "$1" >&2
   tag "$subject" "tagdef active" >&2

   tag "$subject" "tagdef readpolicy" tagpolicy "$4" >&2
   tag "$subject" "tagdef writepolicy" tagpolicy "$5" >&2

   if [[ "$6" == "true" ]]
   then
      tag "$subject" "tagdef multivalue" >&2
   fi

   if [[ -n "$7" ]]
   then
      tag "$subject" "tagdef type" type "$7" >&2
   else
      tag "$subject" "tagdef type" type "$2" >&2
   fi

   if [[ "$8" == "true" ]]
   then
      tag "$subject" "tagdef unique" >&2
   fi
}

tagdef_table()
{
   # args: tagname dbtype owner readpolicy writepolicy multivalue [typestr [primarykey]]

   if [[ -n "$2" ]] && [[ "$2" != empty ]]
   then
      if [[ "$2" = "text" ]]
      then
         default="DEFAULT ''"
      else
         default=""
      fi
      if [[ "$7" = "file" ]]
      then
         fk="REFERENCES \"_latest with name\" (value) ON DELETE CASCADE"
      elif [[ "$7" = "vfile" ]]
      then
         fk="REFERENCES \"_vname\" (value) ON DELETE CASCADE"
      elif [[ "$1" = "vname" ]] || [[ "$8" = true ]]
      then
         fk="UNIQUE"
      else
         fk=""
      fi
      if [[ "$6" = "true" ]]
      then
         uniqueval='UNIQUE(subject, value)'
      else
         uniqueval='UNIQUE(subject)'
      fi

      psql -q -t <<EOF
CREATE TABLE "_$1" ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE, 
                       value $2 ${default} NOT NULL ${fk}, ${uniqueval} );
CREATE INDEX "_$1_value_idx" ON "_$1" (value);
EOF
   else
      psql -q -t <<EOF
CREATE TABLE "_$1" ( subject bigint UNIQUE NOT NULL REFERENCES resources (subject) ON DELETE CASCADE );
EOF
   fi
}

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

   tagdef_table "$@"
}

tagdefs_complete()
{
   local i
   echo ${!tag_names[*]}
   for i in ${!tag_names[*]}
   do
      tagdef_tags "${tag_names[$i]}" "${tag_dbtypes[$i]}" "${tag_owners[$i]}" "${tag_readpolicies[$i]}" "${tag_writepolicies[$i]}" "${tag_multivalues[$i]}" "${tag_typestrs[$i]}" "${tag_uniques[$i]}"
   done
}

typedef()
{
   typename="$1"
   dbtype="$2"
   desc="$3"
   shift 3
   local subject=$(dataset "" typedef "" "*")
   tag "$subject" "typedef" text "${typename}" >&2
   tag "$subject" "typedef dbtype" text "${dbtype}" >&2
   tag "$subject" "typedef description" text "${desc}" >&2
   if [[ $# -gt 0 ]]
   then
      tag "$subject" "typedef values" text "$@" >&2
   fi
}


#      TAGNAME        TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR    PKEY

tagdef 'id'           int8        ""      anonymous   system     false      ""         true
tagdef 'tagdef'       text        ""      anonymous   system     false      ""         true
tagdef 'typedef'      text        ""      anonymous   file       false      ""         true
tagdef 'config'       text        ""      anonymous   file       false      ""         true
tagdef 'view'         text        ""      anonymous   file       false      ""         true

tagdef 'default view' text        ""      file        file       false      viewname

tagdef 'tagdef type'  text        ""      anonymous   system     false      type
tagdef 'tagdef unique' empty      ""      anonymous   system     false      ""

tagdef 'tagdef multivalue'  empty ""      anonymous   system     false
tagdef 'tagdef active'      empty ""      anonymous   system     false
tagdef 'tagdef readpolicy'   text ""      anonymous   system     false      tagpolicy
tagdef 'tagdef writepolicy'  text ""      anonymous   system     false      tagpolicy

tagdef 'tag read users'      text ""      anonymous   fowner     true       rolepat
tagdef 'tag write users'     text ""      anonymous   fowner     true       rolepat

tagdef 'typedef description' text   ""      anonymous   file       false
tagdef 'typedef dbtype' text        ""      anonymous   file       false
tagdef 'typedef values' text        ""      anonymous   file       true

tagdef owner          text        ""      anonymous   fowner     false      role
tagdef created        timestamptz ""      anonymous   system     false
tagdef "version created" timestamptz ""   anonymous   system     false
tagdef "read users"   text        ""      anonymous   fowner     true       rolepat
tagdef "write users"  text        ""      anonymous   fowner     true       rolepat
tagdef "modified by"  text        ""      anonymous   system     false      role
tagdef modified       timestamptz ""      anonymous   system     false
tagdef bytes          int8        ""      anonymous   system     false
tagdef version        int8        ""      anonymous   system     false
tagdef name           text        ""      anonymous   system     false
tagdef 'latest with name' text    ""      anonymous   system     false      ""         true
tagdef vname          text        ""      anonymous   system     false      ""         true
tagdef dtype          text        ""      anonymous   system     false      dtype
tagdef storagename    text        ""      system      system     false      ""         true
tagdef url            text        ""      file        system     false      url
tagdef content-type   text        ""      anonymous   file       false
tagdef sha256sum      text        ""      anonymous   file       false

tagdef contains       text        ""      file        file       true       file
tagdef vcontains      text        ""      file        file       true       vfile
tagdef key            text        ""      anonymous   file       false      ""         true

tagdef "list on homepage" empty   ""      anonymous   tag        false
tagdef "homepage order" int8      ""      anonymous   tag        false
tagdef "Image Set"    empty       "${admin}"   file   file       false

psql -q -t <<EOF
CREATE TABLE subjecttags ( subject bigint REFERENCES resources (subject) ON DELETE CASCADE, tagname text, UNIQUE (subject, tagname) );
EOF

tagdefs_complete

# redefine tagdef to perform both phases, now that core (recursively constrained) tagdefs are in place
tagdef()
{
   tagdef_table "$@"
   tagdef_tags "$@"
}

# add tagdef foreign key referencing constraint
# drop storage for psuedo tag 'id' which we can synthesize from any subject column
psql -e -t <<EOF
ALTER TABLE subjecttags ADD FOREIGN KEY (tagname) REFERENCES _tagdef (value) ON DELETE CASCADE;
DROP TABLE "_id";
EOF

tagacl "list on homepage" read "*"
tagacl "list on homepage" write "${admin}"

tagacl "homepage order" read "*"
tagacl "homepage order" write "${admin}"


homepath="https://${HOME_HOST}/${SVCPREFIX}"

homelinks=(
$(dataset "Manage roles" url "https://${HOME_HOST}/webauthn/roles"               "${admin}")
$(dataset "Manage tag definitions (expert mode)" url "${homepath}/tagdef"        "${admin}")
$(dataset "Create catalog entries (expert mode)" url "${homepath}/file?action=define" "${admin}")
$(dataset "Upload study" url "${homepath}/study?action=upload"                   "${admin}" "${curator}" "${uploader}")
$(dataset "Download study" url "${homepath}/study?action=download"               "${admin}" "${curator}" "${downloader}")
$(dataset "Query by tags, latest versions" url "${homepath}/query?action=edit"   "${admin}" "${curator}" "${downloader}")
$(dataset "Query by tags, all versions" url "${homepath}/query?action=edit&versions=any"   "${admin}" "${curator}" "${downloader}")
$(dataset "View tag definitions" url "${homepath}/query/tagdef?view=tagdef"      "${admin}" "*")
)

i=0
while [[ $i -lt "${#homelinks[*]}" ]]
do
   tag "${homelinks[$i]}" "list on homepage"
   tag "${homelinks[$i]}" "homepage order" int8 "$i"
   i=$(( $i + 1 ))
done

tagfilercfg=$(dataset "tagfiler" config "${admin}" "*")
tag $tagfilercfg "view" text "default"  # config="tagfiler" is also view="default"

typedef empty        ''            'No content'
typedef int8         int8          'Integer'
typedef float8       float8        'Floating point'
typedef date         date          'Date'
typedef timestamptz  timestamptz   'Date and time with timezone'
typedef text         text          'Text'
typedef role         text          'Role'
typedef rolepat      text          'Role pattern'
typedef tagname      text          'Tag name'
typedef tagdef       text          'Tag definition'
typedef dtype        text          'Dataset type' 'blank Metadata-only dataset' 'config Configuration data' 'file Locally stored file' 'contains Collection of unversioned datasets' 'tagdef Tag definition' 'typedef Type definition' 'url URL redirecting dataset' 'vcontains Collection of versioned datasets' 'view View definition'
typedef url          text          'URL'
typedef id           int8          'Dataset ID'
typedef file         text          'Dataset name'
typedef vfile        text          'Dataset name with version number'

typedef tagpolicy    text          'Tag policy model' 'anonymous Any client may access' 'users Any authenticated client may access' 'file Subject authorization is observed' 'fowner Subject owner may access' 'tag Tag authorization is observed' 'system No client can access'

typedef type         text          'Scalar value type'
typedef viewname     text          'View name'

cfgtags=$(dataset "config" view "${admin}" "*")

cfgtagdef()
{
   local tagname="_cfg_$1"
   shift
   tagdef "$tagname" "$@"
   tag "$cfgtags" "_cfg_file list tags" tagname "$tagname"
   [[ "$tagname" == "_cfg_file list tags" ]] ||  tag "$cfgtags" "_cfg_tag list tags" tagname "$tagname"
}

#      TAGNAME        TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR    PKEY

# file list tags MUST BE DEFINED FIRST
cfgtagdef 'file list tags' text     ""      file        file       true       tagname
# tag list tags MUST BE DEFINED NEXT...
cfgtagdef 'tag list tags' text      ""      file        file       true       tagname
# THEN, need to do this manually to break dependency loop
tag "$cfgtags" "_cfg_tag list tags" tagname "_cfg_file list tags"

cfgtagdef 'file list tags write' text ""    file        file       true       tagname
cfgtagdef 'tagdef write users' text ""      file        file       true       rolepat
cfgtagdef 'file write users' text   ""      file        file       true       rolepat
cfgtagdef home          text        ""      file        file       false
cfgtagdef 'webauthn home' text      ""      file        file       false
cfgtagdef 'webauthn require' empty  ""      file        file       false
cfgtagdef 'store path'  text        ""      file        file       false
cfgtagdef 'log path'    text        ""      file        file       false
cfgtagdef 'template path' text      ""      file        file       false
cfgtagdef 'chunk bytes' int8        ""      file        file       false
cfgtagdef 'local files immutable' empty ""  file        file       false
cfgtagdef 'remote files immutable' empty "" file        file       false
cfgtagdef 'policy remappings' text  ""      file        file       true
cfgtagdef subtitle      text        ""      file        file       false
cfgtagdef logo          text        ""      file        file       false
cfgtagdef contact       text        ""      file        file       false
cfgtagdef help          text        ""      file        file       false
cfgtagdef bugs          text        ""      file        file       false
cfgtagdef 'client connections' int8 ""      file        file       false
cfgtagdef 'client upload chunks' empty ""   file        file       false
cfgtagdef 'client download chunks' empty "" file        file       false
cfgtagdef 'client socket buffer size' int8 "" file      file       false
cfgtagdef 'client chunk bytes' int8 ""      file        file       false
cfgtagdef 'applet tags' text        ""      file        file       true       tagname
cfgtagdef 'applet tags require' text ""     file        file       true       tagname
cfgtagdef 'applet custom properties' text "" file       file       true
cfgtagdef 'applet test log' text    ""      file        file       false
cfgtagdef 'applet test properties' text ""  file        file       true

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
#cfgtag "chunk bytes" text '1048576'

cfgtag "client connections" int8 '4'
cfgtag "client upload chunks"
cfgtag "client download chunks"
cfgtag "client socket buffer size" int8 '8192'
cfgtag "client chunk bytes" int8 '4194304'

cfgtag "file write users" text "*" "admin"
cfgtag "tagdef write users" text "*" "admin"

cfgtag "file list tags" text bytes owner 'read users' 'write users'
cfgtag "file list tags write" text 'read users' 'write users' 'owner'

#cfgtag "applet tags" text ...
#cfgtag "applet tags require" text ...
#cfgtag "applet properties" text 'tagfiler.properties'

#cfgtag "local files immutable"
#cfgtag "remote files immutable"

tagdeftags=$(dataset "tagdef" view "${admin}" "*")
for tagname in "tagdef type" "tagdef multivalue" "tagdef readpolicy" "tagdef writepolicy" "tag read users" "tag write users" "read users" "write users"
do
   tag "$tagdeftags" "_cfg_file list tags" "tagname" "$tagname"
   tag "$tagdeftags" "_cfg_tag list tags" "tagname" "$tagname"
done

typedeftags=$(dataset "typedef" view "${admin}" "*")
for tagname in "typedef description" "typedef dbtype" "typedef values"
do
   tag "$typedeftags" "_cfg_file list tags" "tagname" "$tagname"
   tag "$typedeftags" "_cfg_tag list tags" "tagname" "$tagname"
done

viewtags=$(dataset "view" view "${admin}" "*")
for tagname in "_cfg_file list tags" "_cfg_file list tags write" "_cfg_tag list tags"
do
   tag "$viewtags" "_cfg_file list tags" "tagname" "$tagname"
   tag "$viewtags" "_cfg_tag list tags" "tagname" "$tagname"
done

# remapping rules:
#  srcrole ; dstrole ; reader, ... ; writer, ...
# semi-colons required but readers and writers optional, e.g. srcrole;dstrole;;

# these are actual (not logical) role names just like other ACLs and metadata
# only the python code itself uses logical roles for built-in policies

if [[ "${uploader}" = "${curator}" ]]
then
   writers=
else
   # allow uploader to retain access
   writers="${uploader}"
   readers="${uploader}"
fi

if [[ "${downloader}" = "${curator}" ]]
then
   readers=
else
   # also give read access to downloaders
   if [[ -n "${readers}" ]]
   then
      readers="${readers},${downloader}"
   else
      readers="${downloader}"
   fi
fi

cfgtag "policy remappings" text "${uploader};${curator};${readers};${writers}"

#cfgtag "applet test properties" text '/home/userid/appletTest.properties'
#cfgtag "applet test log" text '/home/userid/applet.log'

cfgtag "subtitle" text "Tagfiler (trunk) on ${HOME_HOST}"
cfgtag "logo" text '<img alt="tagfiler" title="Tagfiler (trunk)" src="/'"${SVCPREFIX}"'/static/logo.png" width="245" height="167" />'
cfgtag "contact" text '<p>Your HTML here</p>'
cfgtag "help" text 'https://confluence.misd.isi.edu:8443/display/DEIIMGUP/Home'
cfgtag "bugs" text 'https://jira.misd.isi.edu/browse/DEIIMGUP'


#. ./dbsetup-nei-demo.sh

