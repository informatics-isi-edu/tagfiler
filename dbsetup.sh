#!/bin/sh

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
CREATE TABLE files ( name text, version int8, PRIMARY KEY(name, version) );
CREATE TABLE latestfiles ( name text PRIMARY KEY, version int8, FOREIGN KEY (name, version) REFERENCES files (name, version) ON DELETE CASCADE );
CREATE SEQUENCE transmitnumber;
CREATE SEQUENCE keygenerator;
EOF

# pre-established stored data
dataset()
{
   # args: <name> url <url> <owner> [<readuser>]...
   # args: <name> blank <owner> [<readuser>]...
   # args: <name> typedef <owner> [<readuser>]...
   # args: <name> tagdef <owner> [<readuser>]...

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
      blank|typedef|tagdef)
         :
         ;;
      *)
         echo "Unsupported dataset format: $*"
         exit 1
         ;;
   esac

   local owner="$1"
   shift

   echo "create $type dataset: '$file'"

   psql -t -q <<EOF
INSERT INTO files (name, version) VALUES ( '$file', 1 );
INSERT INTO latestfiles (name, version) VALUES ( '$file', 1 );
EOF

   tag "$file" name text "$file"
   tag "$file" vname text "$file@1"
   tag "$file" version int8 1
   tag "$file" dtype text "$type"
   tag "$file" owner text "$owner"

   while [[ $# -gt 0 ]]
   do
      tag "$file" "read users" text "$1"
      shift
   done

   case "$type" in
      url)
         tag "$file" url text "$url"
         ;;
   esac
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
INSERT INTO "_$tagname" ( file, version ) VALUES ( '$file', 1 );
EOF
   elif [[ $# -gt 0 ]]
   then
      while [[ $# -gt 0 ]]
      do
	cat <<EOF
INSERT INTO "_$tagname" ( file, version, value ) VALUES ( '$file', 1, '$1' );
EOF
         shift
      done
   fi | psql -q -t

   # add to filetags only if this insert changes status
   untracked=$(psql -A -t -q <<EOF
SELECT DISTINCT a.file 
FROM "_$tagname" AS a 
LEFT OUTER JOIN filetags AS b ON (a.file = b.file AND a.version = b.version AND b.tagname = '$tagname')
WHERE b.file IS NULL;
EOF
)

   if [[ -n "$untracked" ]]
   then
      psql -q -t <<EOF
INSERT INTO filetags (file, version, tagname) VALUES ('$file', 1, '$tagname');
EOF
   fi
}

tagacl()
{
   # args: tagname {read|write} [value]...
   local tag=$1
   local mode=$2
   shift 2
   while [[ $# -gt 0 ]]
   do
      tag "_tagdef_$tag" "tag $mode users" rolepat "$1"
      shift
   done
}

tagdef_tags()
{
   # args: tagname dbtype owner readpolicy writepolicy multivalue [typestr]

   # policy is one of:
   #   anonymous  -- any client can access
   #   users  -- any authenticated user can access
   #   file  -- file access rule is observed for tag access
   #   fowner  -- only file owner can access
   #   tag -- tag access rule is observed for tag access
   #   system  -- no client can access

   echo "create tagdef '$1'..."

   dataset "_tagdef_$1" tagdef "$3" "*"

   tag "_tagdef_$1" "tagdef" text "$1"
   tag "_tagdef_$1" "tagdef active"

   tag "_tagdef_$1" "tagdef readpolicy" tagpolicy "$4"
   tag "_tagdef_$1" "tagdef writepolicy" tagpolicy "$5"

   if [[ "$6" == "true" ]]
   then
      tag "_tagdef_$1" "tagdef multivalue"
   fi

   if [[ -n "$7" ]]
   then
      tag "_tagdef_$1" "tagdef type" type "$7"
   else
      tag "_tagdef_$1" "tagdef type" type "$2"
   fi
}

tagdef_table()
{
   # args: tagname dbtype owner readpolicy writepolicy multivalue [typestr [primarykey]]

   if [[ -n "$2" ]]
   then
      if [[ "$2" = "text" ]]
      then
         default="DEFAULT ''"
      else
         default=""
      fi
      if [[ "$7" = "file" ]]
      then
         fk="REFERENCES latestfiles (name) ON DELETE CASCADE"
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
         uniqueval='UNIQUE(file, version, value)'
      else
         uniqueval='UNIQUE(file, version)'
      fi

      psql -q -t <<EOF
CREATE TABLE "_$1" ( file text NOT NULL, 
                       version int8 NOT NULL,
                       value $2 ${default} NOT NULL ${fk}, ${uniqueval} ,
                       FOREIGN KEY (file, version) REFERENCES files (name, version) ON DELETE CASCADE );
CREATE INDEX "_$1_value_idx" ON "_$1" (value);
EOF
   else
      psql -q -t <<EOF
CREATE TABLE "_$1" ( file text NOT NULL, version int8 NOT NULL, UNIQUE (file, version), FOREIGN KEY (file, version) REFERENCES files (name, version) ON DELETE CASCADE );
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

   tagdef_table "$@"
}

tagdefs_complete()
{
   local i
   echo ${!tag_names[*]}
   for i in ${!tag_names[*]}
   do
      tagdef_tags "${tag_names[$i]}" "${tag_dbtypes[$i]}" "${tag_owners[$i]}" "${tag_readpolicies[$i]}" "${tag_writepolicies[$i]}" "${tag_multivalues[$i]}" "${tag_typestrs[$i]}"
   done
}

typedef()
{
   typename="$1"
   dbtype="$2"
   desc="$3"
   shift 3
   dataset "_type_def_${typename}" typedef "${admin}" "*"
   tag "_type_def_${typename}" "typedef" text "${typename}"
   tag "_type_def_${typename}" "_type_dbtype" text "${dbtype}"
   tag "_type_def_${typename}" "_type_description" text "${desc}"
   if [[ $# -gt 0 ]]
   then
      tag "_type_def_${typename}" "_type_values" text "$@"
   fi
}


#      TAGNAME        TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR    PKEY

tagdef 'tagdef'       text        ""      anonymous   system     false      ""         true
tagdef 'typedef'      text        ""      anonymous   file       false

tagdef 'tagdef type'         text ""      anonymous   system     false      type

tagdef 'tagdef multivalue'   ""   ""      anonymous   system     false
tagdef 'tagdef active'      ""   ""      anonymous   system     false
tagdef 'tagdef readpolicy'   text ""      anonymous   system     false      tagpolicy
tagdef 'tagdef writepolicy'  text ""      anonymous   system     false      tagpolicy
tagdef 'tag read users'      text ""      anonymous   system     true       rolepat
tagdef 'tag write users'     text ""      anonymous   system     true       rolepat

tagdef '_type_description' text   ""      anonymous   file       false
tagdef '_type_dbtype' text        ""      anonymous   file       false
tagdef '_type_values' text        ""      anonymous   file       true

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
tagdef vname          text        ""      anonymous   system     false
tagdef dtype          text        ""      anonymous   system     false      dtype
tagdef storagename    text        ""      system      system     false
tagdef url            text        ""      file        system     false      url
tagdef content-type   text        ""      anonymous   file       false
tagdef sha256sum      text        ""      anonymous   file       false

tagdef contains       text        ""      file        file       true       file
tagdef vcontains      text        ""      file        file       true       vfile
tagdef key            text        ""      anonymous   file       false
tagdef "member of"    text        ""      anonymous   file       true

tagdef "list on homepage" ""      ""      anonymous   tag        false
tagdef "Image Set"    ""          "${admin}"   file   file       false

psql -q -t <<EOF
CREATE TABLE filetags ( file text, version int8, tagname text, UNIQUE (file, version, tagname), FOREIGN KEY (file, version) REFERENCES files (name, version) ON DELETE CASCADE );
EOF

tagdefs_complete

# redefine tagdef to perform both phases, now that core (recursively constrained) tagdefs are in place
tagdef()
{
   tagdef_table "$@"
   tagdef_tags "$@"
}

psql -e -t <<EOF
ALTER TABLE filetags ADD FOREIGN KEY (tagname) REFERENCES _tagdef (value) ON DELETE CASCADE;
EOF

tagacl "list on homepage" read "*"
tagacl "list on homepage" write "${admin}"

dataset "New image studies" url 'Image%20Set;Downloaded:not:?view=study%20tags' "${admin}" "${downloader}"
dataset "Previous image studies" url 'Image%20Set;Downloaded?view=study%20tags' "${admin}" "${downloader}"
dataset "All image studies" url 'Image%20Set?view=study%20tags' "${admin}" "${downloader}"

for x in "New image studies" "Previous image studies" "All image studies"
do
   tag "$x" "list on homepage"
done

dataset "tagfiler configuration" url "https://${HOME_HOST}/${SVCPREFIX}/tags/tagfiler%20configuration?view=configuration%20tags" "${admin}" "*"

typedef ''           ''            'No content'
typedef int8         int8          'Integer'
typedef float8       float8        'Floating point'
typedef date         date          'Date'
typedef timestamptz  timestamptz   'Date and time with timezone'
typedef text         text          'Text'
typedef role         text          'Role'
typedef rolepat      text          'Role pattern'
typedef tagname      text          'Tag name'
typedef dtype       text          'Dataset type' 'url URL redirecting dataset' 'blank Metadata-only dataset' 'typedef Type definition' 'tagdef Tag definition' 'file Locally stored file' 'contains Collection of unversioned datasets' 'vcontains Collection of versioned datasets'
typedef url          text          'URL'
typedef file         text          'Dataset'
typedef vfile        text          'Dataset with version number'

typedef tagpolicy    text          'Tag policy model' 'anonymous Any client may access' 'users Any authenticated client may access' 'file Subject authorization is observed' 'fowner Subject owner may access' 'tag Tag authorization is observed' 'system No client can access'

typedef type         text          'Scalar value type'




dataset "configuration tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/configuration%20tags" "${admin}" "*"

cfgtagdef()
{
   local tagname="_cfg_$1"
   shift
   tagdef "$tagname" "$@"
   tag "configuration tags" "_cfg_file list tags" tagname "$tagname"
   [[ "$tagname" == "_cfg_file list tags" ]] ||  tag "configuration tags" "_cfg_tag list tags" tagname "$tagname"
}

#         TAGNAME       TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR

# file list tags MUST BE DEFINED FIRST
cfgtagdef 'file list tags' text     ""      file        file       true       tagname
# tag list tags MUST BE DEFINED NEXT...
cfgtagdef 'tag list tags' text      ""      file        file       true       tagname
# THEN, need to do this manually to break dependency loop
tag "configuration tags" "_cfg_tag list tags" tagname "_cfg_file list tags"

cfgtagdef 'file list tags write' text ""    file        file       true       tagname
cfgtagdef home          text        ""      file        file       false
cfgtagdef 'webauthn home' text      ""      file        file       false
cfgtagdef 'webauthn require' text   ""      file        file       false
cfgtagdef 'store path'  text        ""      file        file       false
cfgtagdef 'log path'    text        ""      file        file       false
cfgtagdef 'template path' text      ""      file        file       false
cfgtagdef 'chunk bytes' text        ""      file        file       false
cfgtagdef 'local files immutable' text ""   file        file       false
cfgtagdef 'remote files immutable' text ""  file        file       false
cfgtagdef 'policy remappings' text  ""      file        file       true
cfgtagdef subtitle      text        ""      file        file       false
cfgtagdef logo          text        ""      file        file       false
cfgtagdef contact       text        ""      file        file       false
cfgtagdef help          text        ""      file        file       false
cfgtagdef bugs          text        ""      file        file       false
cfgtagdef 'client connections' text ""      file        file       false
cfgtagdef 'client upload chunks' text ""    file        file       false
cfgtagdef 'client download chunks' text ""  file        file       false
cfgtagdef 'client socket buffer size' text "" file      file       false
cfgtagdef 'client chunk bytes' text ""      file        file       false
cfgtagdef 'applet tags' text        ""      file        file       true       tagname
cfgtagdef 'applet tags require' text ""     file        file       true       tagname
cfgtagdef 'applet custom properties' text "" file       file       false
cfgtagdef 'applet test log' text    ""      file        file       false
cfgtagdef 'applet test properties' text ""  file        file       true

cfgtag()
{
   tagname="_cfg_$1"
   shift
   tag "tagfiler configuration" "$tagname" "$@"
}

#cfgtag "home" text 'https://${HOME_HOST}'
cfgtag "webauthn home" text "https://${HOME_HOST}/webauthn"
cfgtag "webauthn require" text 'True'

#cfgtag "store path" text '${DATADIR}'
#cfgtag "log path" text '${LOGDIR}'
#cfgtag "template path" text '${TAGFILERDIR}/templates'
#cfgtag "chunk bytes" text '1048576'

cfgtag "client connections" text '4'
cfgtag "client upload chunks" text 'True'
cfgtag "client download chunks" text 'True'
cfgtag "client socket buffer size" text '8192'
cfgtag "client chunk bytes" text '4194304'

cfgtag "file list tags" text dtype bytes owner 'read users' 'write users'
#cfgtag "file list tags write" text 'read users' 'write users'
#cfgtag "applet tags" text ...
#cfgtag "applet tags require" text ...
#cfgtag "applet properties" text 'tagfiler.properties'

#cfgtag "local files immutable" text 'True'
#cfgtag "remote files immutable" text 'True'

dataset "tagdef tags" blank "${admin}" "*"
for tagname in tagdef "tagdef type" "tagdef multivalue" "tagdef readpolicy" "tagdef writepolicy" "tag read users" "tag write users" "read users" "write users"
do
   tag "tagdef tags" "_cfg_file list tags" "tagname" "$tagname"
   tag "tagdef tags" "_cfg_tag list tags" "tagname" "$tagname"
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

