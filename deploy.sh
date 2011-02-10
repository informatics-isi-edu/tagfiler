#!/bin/sh

######
# NOTE: you can leave all this as defaults and modify Makefile
# which invokes this with SVCPREFIX...
######

# role mapping used in default data and ACLs

# default for trial-data demo
admin=${admin:-admin}
uploader=${uploader:-uploader}
downloader=${downloader:-downloader}
curator=${curator:-coordinator}
grader=${grader:-grader}

# alternates
#admin=MISD
#uploader=PSOC
#downloader=PSOC
#curator=PSOC
#grader=PSOC

TAGFILERDIR=`python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()'`/tagfiler

# this is the URL base path of the service
SVCPREFIX=${1:-tagfiler}

APPLETBUILD=${2}

# you can set this to override...
HOME_HOST=

# default to `hostname` setting
HOST=$(hostname)
HOME_HOST=${HOME_HOST:-$HOST}

# this is the privileged postgresql user for createdb etc.
PGADMIN=postgres

# this is the service daemon account
SVCUSER=${SVCPREFIX}

SVCDIR=/var/www/${SVCPREFIX}
DATADIR=${SVCDIR}-data
RUNDIR=/var/run/wsgi
LOGDIR=${SVCDIR}-logs

# location of platform installed file
PGCONF=/var/lib/pgsql/data/postgresql.conf

# set the services to run automatically?
chkconfig httpd on
chkconfig postgresql on

# finish initializing system for our service
mkdir -p ${DATADIR}
mkdir -p ${RUNDIR}
mkdir -p ${LOGDIR}

if ! runuser -c "/bin/true" ${SVCUSER}
then
    useradd -m -r ${SVCUSER}
fi

chown ${SVCUSER}: ${DATADIR}
chmod og=rx ${DATADIR}
chown ${SVCUSER}: ${LOGDIR}
chmod og= ${LOGDIR}

# try some blind database setup as well
if grep -e '^extra_float_digits = 2[^0-9].*' < ${PGCONF}
then
    :
else
    # need to set extra_float_digits = 2 for proper floating point handling
    PGCONFTMP=${PGCONF}.tmp.$$
    runuser -c "sed -e 's|^.*\(extra_float_digits[^=]*= *\)[-0-9]*\([^#]*#.*\)|\1 2  \2|' < $PGCONF > $PGCONFTMP" - ${PGADMIN} \
	&& mv $PGCONFTMP $PGCONF
    chmod u=rw,og= $PGCONF
fi

service postgresql restart

if runuser -c "psql -c 'select * from pg_user' ${PGADMIN}" - ${PGADMIN} | grep ${SVCUSER} 1>/dev/null
then
    :
else
	runuser -c "createuser -S -D -R ${SVCUSER}" - ${PGADMIN}
fi

runuser -c "dropdb ${SVCUSER}" - ${PGADMIN}
runuser -c "createdb ${SVCUSER}" - ${PGADMIN}


# create local helper scripts
mkdir -p /etc/httpd/passwd

cat > ${HOME}/README-${SVCPREFIX} <<EOF
This service requires passwords to be configured via:

  htdigest /etc/httpd/passwd/passwd "${SVCUSER}" username

for each user you wish to add.

EOF

cat > /home/${SVCUSER}/dbsetup.sh <<EOF
#!/bin/sh

# this script will recreate all tables, but only on a clean database

echo "create core tables..."

psql -q -t -c "CREATE TABLE files ( name text, version int8, PRIMARY KEY(name, version) )"
psql -q -t -c "CREATE TABLE latestfiles ( name text PRIMARY KEY, version int8, FOREIGN KEY (name, version) REFERENCES files (name, version) ON DELETE CASCADE )"
psql -q -t -c "CREATE TABLE filetags ( file text, version int8, tagname text REFERENCES tagdefs (tagname) ON DELETE CASCADE, UNIQUE (file, version, tagname), FOREIGN KEY (file, version) REFERENCES files (name, version) ON DELETE CASCADE )"

psql -q -t -c "CREATE SEQUENCE transmitnumber"
psql -q -t -c "CREATE SEQUENCE keygenerator"

# pre-established stored data
dataset()
{
   # args: <name> url <url> <owner> [<readuser>]...
   # args: <name> blank <owner> [<readuser>]...
   # args: <name> typedef <owner> [<readuser>]...

   local file="\$1"
   local type="\$2"
   local url
   local owner

   shift 2

   case "\$type" in
      url)
         url="\$1"
         shift         

         case "\$url" in
            http*:*|/*)
               url="\$url"
               ;;
            *)
               url="https://${HOME_HOST}/${SVCPREFIX}/query/\$url"
              ;;
         esac
         ;;
      blank|typedef)
         :
         ;;
      *)
         echo "Unsupported dataset format: $*"
         exit 1
         ;;
   esac

   local owner="\$1"
   shift

   echo "create \$type dataset: '\$file'"

   psql -t -q -c "INSERT INTO files (name, version) VALUES ( '\$file', 1 )"
   psql -t -q -c "INSERT INTO latestfiles (name, version) VALUES ( '\$file', 1 )"
   tag "\$file" name text "\$file"
   tag "\$file" vname text "\$file@1"
   tag "\$file" version int8 1
   tag "\$file" dtype text "\$type"
   tag "\$file" owner text "\$owner"

   while [[ \$# -gt 0 ]]
   do
      tag "\$file" "read users" text "\$1"
      shift
   done

   case "\$type" in
      url)
         tag "\$file" url text "\$url"
         ;;
   esac
}

tag()
{
   # args: file tag typestr [value]...
   # for non-empty typestr
   #     does one default value insert for 0 values
   #     does N value inserts for N>0 values

   local file="\$1"
   local tagname="\$2"
   local typestr="\$3"

   shift 3

   echo "set /tags/\$file/\$tagname=" "\$@"
   if [[ -z "\$typestr" ]] || [[ \$# -eq 0 ]]
   then
      psql -q -t -c "INSERT INTO \\"_\$tagname\\" ( file, version ) VALUES ( '\$file', 1 )"
   elif [[ \$# -gt 0 ]]
   then
      while [[ \$# -gt 0 ]]
      do
         psql -q -t -c "INSERT INTO \\"_\$tagname\\" ( file, version, value ) VALUES ( '\$file', 1, '\$1' )"
         shift
      done
   fi

   # add to filetags only if this insert changes status
   if [[ -z "\$(psql -A -t -c "SELECT * FROM filetags WHERE file = '\$file' AND version = 1 AND tagname = '\$tagname'")" ]] \
     && [[ -n "\$(psql -A -t -c "SELECT * FROM \\"_\$tagname\\" WHERE file = '\$file' AND version = 1 ")" ]]
   then
      psql -q -t -c "INSERT INTO filetags (file, version, tagname) VALUES ('\$file', 1, '\$tagname')"
   fi
}

tagacl()
{
   # args: tagname {read|write} [value]...
   local tag=\$1
   local mode=\$2
   shift 2
   while [[ \$# -gt 0 ]]
   do
      tag "_tagdef_\$tag" "tag \$mode users" rolepat "\$1"
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

   echo "create tagdef '\$1'..."

   dataset "_tagdef_\$1" blank "\$3" "*"

   tag "_tagdef_\$1" "tagdef readpolicy" "\$4"
   tag "_tagdef_\$1" "tagdef writepolicy" "\$5"

   if [[ "\$6" == "true" ]]
   then
      tag "_tagdef_\$1" "tagdef multivalue"
   fi

   if [[ -n "\$7" ]]
   then
      tag "_tagdef_\$1" "tagdef type" "\$7"
   else
      tag "_tagdef_\$1" "tagdef type" "\$2"
   fi
}

tagdef_table()
{
   # args: tagname dbtype owner readpolicy writepolicy multivalue [typestr]

   if [[ -n "\$2" ]]
   then
      if [[ "\$2" = "text" ]]
      then
         default="DEFAULT ''"
      else
         default=""
      fi
      if [[ "\$7" = "file" ]]
      then
         fk="REFERENCES latestfiles (name) ON DELETE CASCADE"
      elif [[ "\$7" = "vfile" ]]
      then
         fk="REFERENCES \"_vname\" (value) ON DELETE CASCADE"
      elif [[ "\$1" = "vname" ]]
      then
         fk="UNIQUE"
      else
         fk=""
      fi
      if [[ "\$6" = "true" ]]
      then
         uniqueval='UNIQUE(file, version, value)'
      else
         uniqueval='UNIQUE(file, version)'
      fi
      psql -q -t -c "CREATE TABLE \\"_\$1\\" ( file text NOT NULL, version int8 NOT NULL, value \$2 \${default} NOT NULL \${fk}, \${uniqueval} , FOREIGN KEY (file, version) REFERENCES files (name, version) ON DELETE CASCADE )"
      psql -q -t -c "CREATE INDEX \\"_\$1_value_idx\\" ON \\"_\$1\\" (value)"
   else
      psql -q -t -c "CREATE TABLE \\"_\$1\\" ( file text NOT NULL, version int8 NOT NULL, UNIQUE (file, version), FOREIGN KEY (file, version) REFERENCES files (name, version) ON DELETE CASCADE )"
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
   tag_names[${#tag_names[*]}]="\$1"
   tag_dbtypes[${#tag_dbtypes[*]}]="\$2"
   tag_owners[${#tag_owners[*]}]="\$3"
   tag_readpolicies[${#tag_readpolicies[*]}]="\$4"
   tag_writepolicies[${#tag_writepolicies[*]}]="\$5"
   tag_multivalues[${#tag_multivalues[*]}]="\$6"
   tag_typestrs[${#tag_typestrs[*]}]="\$7"

   tagdef_table "\$@"
}

tagdefs_complete()
{
   for i in \${!tag_names[*]}
   do
      tagdef_table "\${tag_names[\$i]}" "\${tag_dbtypes[\$i]}" "\${tag_owners[\$i]}" "\${tag_readpolicies[\$i]}" "\${tag_writepolicies[\$i]}" "\${tag_multivalues[\$i]}" "\${tag_typestrs[\$i]}"
   done
}

typedef()
{
   typename="\$1"
   dbtype="\$2"
   desc="\$3"
   shift 3
   dataset "_type_def_\${typename}" typedef "${admin}" "*"
   tag "_type_def_\${typename}" "typedef" text "\${typename}"
   tag "_type_def_\${typename}" "_type_dbtype" text "\${dbtype}"
   tag "_type_def_\${typename}" "_type_description" text "\${desc}"
   if [[ \$# -gt 0 ]]
   then
      tag "_type_def_\${typename}" "_type_values" text "\$@"
   fi
}


#      TAGNAME        TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR

tagdef 'tagdef'       text        ""      anonymous   system     false
tagdef 'typedef'      text        ""      anonymous   file       false

tagdef 'tagdef type'         text ""      anonymous   system     false      type
tagdef 'tagdef multivalue'   ""   ""      anonymous   system     false
tagdef 'tagdef readpolicy'   text ""      anonymous   system     false      tagpolicy
tagdef 'tagdef writepolicy'  text ""      anonymous   system     false      tagpolicy
tagdef 'tag read users'      text ""      anonymous   system     false      rolepat
tagdef 'tag write users'     text ""      anonymous   system     false      rolepat

tagdef '_type_description' text   ""      anonymous   file       false
tagdef '_type_dbtype' text        ""      anonymous   file       false
tagdef '_type_values' text        ""      anonymous   file       true

tagdef 'tagdef type'  text        ""      anonymous   system

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
tagdef "Image Set"    ""          "${admin}"   file        file       false

tagdefs_complete

tagacl "list on homepage" read "*"
tagacl "list on homepage" write "${admin}"

dataset "New image studies" url 'Image%20Set;Downloaded:not:?view=study%20tags' "${admin}" "${downloader}"
dataset "Previous image studies" url 'Image%20Set;Downloaded?view=study%20tags' "${admin}" "${downloader}"
dataset "All image studies" url 'Image%20Set?view=study%20tags' "${admin}" "${downloader}"

for x in "New image studies" "Previous image studies" "All image studies"
do
   tag "\$x" "list on homepage"
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
typedef dtype       text          'Dataset type' 'url URL redirecting dataset' 'blank Metadata-only dataset' 'typedef Type definition' 'file Locally stored file' 'contains Collection of unversioned datasets' 'vcontains Collection of versioned datasets'
typedef url          text          'URL'
typedef file         text          'Dataset'
typedef vfile        text          'Dataset with version number'

typedef type         text          'Scalar value type'


dataset "configuration tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/configuration%20tags" "${admin}" "*"

cfgtagdef()
{
   local tagname="_cfg_\$1"
   shift
   tagdef "\$tagname" "\$@"
   tag "configuration tags" "_cfg_file list tags" tagname "\$tagname"
   [[ "\$tagname" == "_cfg_file list tags" ]] ||  tag "configuration tags" "_cfg_tag list tags" tagname "\$tagname"
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
   tagname="_cfg_\$1"
   shift
   tag "tagfiler configuration" "\$tagname" "\$@"
}

#cfgtag "home" text 'https://${HOME_HOST}'
cfgtag "webauthn home" text 'https://${HOME_HOST}/webauthn'
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
   if [[ -n "\${readers}" ]]
   then
      readers="\${readers},${downloader}"
   else
      readers="${downloader}"
   fi
fi

cfgtag "policy remappings" text "${uploader};${curator};\${readers};\${writers}"

#cfgtag "applet test properties" text '/home/userid/appletTest.properties'
#cfgtag "applet test log" text '/home/userid/applet.log'

cfgtag "subtitle" text 'Tagfiler (trunk) on ${HOME_HOST}'
cfgtag "logo" text '<img alt="tagfiler" title="Tagfiler (trunk)" src="/${SVCPREFIX}/static/logo.png" width="245" height="167" />'
cfgtag "contact" text '<p>Your HTML here</p>'
cfgtag "help" text 'https://confluence.misd.isi.edu:8443/display/DEIIMGUP/Home'
cfgtag "bugs" text 'https://jira.misd.isi.edu/browse/DEIIMGUP'


## Types and Tags for NEI MISD/DEI demo...

tagdef "Downloaded"   ""          ""      tag         tag        false
tagacl "Downloaded" read "${downloader}"
tagacl "Downloaded" write "${downloader}"

dataset "study tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/study%20tags" "${admin}" "*"
dataset "fundus tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/fundus%20tags" "${admin}" "*"
dataset "fundus brief tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/fundus%20brief%20tags" "${admin}" "*"

modtagdef()
{
   local modality="\$1"
   local tagname="\$2"
   shift 2
   tagdef "\$tagname" "\$@"
   tag "\$modality tags" "_cfg_file list tags" tagname "\$tagname"
   tag "\$modality tags" "_cfg_tag list tags" tagname "\$tagname"
   tagacl "\$tagname" read "${downloader}"
   tagacl "\$tagname" write "${grader}"
}

typedef Modality            text 'Modality' 'fundus fundus'
typedef 'Study Name'        text 'Study Name' 'CHES CHES' 'MEPED MEPED' 'LALES LALES'

# fundus
typedef '# 0-9'             int8 'Count (0-9)' '0 0' '1 1' '2 2' '3 3' '4 4' '5 5' '6 6' '7 7' '8 8' '9 9'
typedef '# 0-16'            int8 'Count (0-16)' '0 0' '1 1' '2 2' '3 3' '4 4' '5 5' '6 6' '7 7' '8 8' '9 9' '10 10' '11 11' '12 12' '13 13' '14 14' '15 15' '16 16'
typedef 'no/yes'            int8 'Grade (no/yes)' '0 No' '2 Yes'
typedef 'no/yes/CG'         int8 'Grade (no/yes/CG)' '0 No' '2 Yes' '8 CG'
typedef 'Max DRU Size'      int8 'Grade (Max DRU Size)' '0 None' '1 Questionable/HI' '2 <C0' '3 <C1' '4 <C2' '5 C2' '6 Retic' '8 CG'
typedef 'DRU Area'          int8 'Grade (DRU Area)' '0 None/NA' '10 <63 (C0)' '20 <105' '25 <125 (C1)' '30 <250 (C2)' '35 <350 (I2)' '40 <500' '45 <650 (O2)' '50 <0.5 DA' '60 <1 DA' '70 1 DA' '8 CG'
typedef 'Max DRU Type'      int8 'Grade (Max DRU Type)' '0 None' '1 HI' '2 HD' '3 SD' '4 SI/Retic' '8 CG'
typedef 'DRU Grid Type'     int8 'Grade (DRU Grid Type)' '0 Absent' '1 Questionable' '2 Present' '3 Predom/#' '8 CG'
typedef 'Inc Pigment'       int8 'Grade (Inc Pigment)' '0 None' '1 Questionable' '2 <C0' '3 <C1' '4 <C2' '5 <O2' '6 O2' '7 Pig/Other' '8 CG'
typedef 'RPE Depigment'     int8 'Grade (RPE Depigment)' '0 None' '1 Questionable' '20 <C1' '30 <C2' '35 <I2' '40 <O2' '50 <0.5DA' '60 <1DA' '70 1DA' '8 CG'
typedef 'Inc/RPE Lesions'   int8 'Grade (Inc/RPE)' '0 N' '1 Q' '2 CC' '3 CPT' '8 CG'
typedef 'GA/Ex DA Lesions'  int8 'Grade (GA/Ex DA)' '0 N' '1 Q' '2 Y' '3 CC' '4 CPT' '8 CG'
typedef 'Other Lesions'     int8 'Grade (Other w/o PT)' '0 N' '1 Q' '2 Y' '8 CG'
typedef 'Other Lesions +PT' int8 'Grade (Other w/ PT)' '0 N' '1 Q' '2 Y' '3 PT' '8 CG'
typedef 'Diabetic Retinopathy Level' int8 'Grade (Diabetic Retinopathy Level)' '10 DR Abset' '12 Non-Diabetic' '13 Questionable' '14 HE, SE, IRMA w/o MAs' '15 Hem Only w/o MAs' '20 Microaneurysms Only' '31 Mild NPDR' '37 Mild/Moderate NPDR' '43 Moderate NPDR' '47 Moderate/Severe NPDR' '53 Severe NPDR' '60 FP Only' '61 No Ret w/ RX' '62 MAs Only w/ RX' '63 Early NPDR w/ RX' '64 Moderate/Severe NPDR w/ RX' '65 Moderate PDR' '71 DRS HRC' '75 Severe DRS HRC' '81 Advanced PDR' '85 End-Stage PDR' '90 Cannot Grade'

#        TAGNAME                      TYPE   OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR
tagdef   Modality                     text   "${admin}"   tag         tag        false      Modality
tag "fundus tags" "_cfg_file list tags" tagname "Modality"

tagdef   'Study Name'                 text   "${admin}"   tag         tag        false      'Study Name'
tagdef   'Study Participant'          text   "${admin}"   tag         tag        false
tagdef   'Study Date'                 date   "${admin}"   tag         tag        false

for tag in 'Modality' 'Study Name' 'Study Participant' 'Study Date'
do
   tagacl "\$tag" read PI "${downloader}"
   tagacl "\$tag" write tagger "${coordinator}"
done

# set default applet tags and configure named views too...
cfgtag "applet tags" tagname  "Modality" "Study Name" "Study Participant" "Study Date"
cfgtag "applet tags require" tagname  "Modality" "Study Name" "Study Participant" "Study Date"

for tag in '_cfg_file list tags' '_cfg_file list tags write' '_cfg_applet tags' '_cfg_applet tags require'
do 
   tag 'study tags' "\$tag" tagname "Modality" "Study Name" "Study Participant" "Study Date"
done


#         MOD    TAGNAME                      TYPE   OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR
modtagdef fundus    'Max DRU Size'               int8   "${admin}"   tag         tag        false      'Max DRU Size'
modtagdef fundus    '# DRU Size Subfields'       int8   "${admin}"   tag         tag        false      '# 0-9'
modtagdef fundus    'DRU Area'                   int8   "${admin}"   tag         tag        false      'DRU Area'
modtagdef fundus    'Max DRU Type'               int8   "${admin}"   tag         tag        false      'Max DRU Type'
modtagdef fundus    '# DRU Type Subfields'       int8   "${admin}"   tag         tag        false      '# 0-9'
modtagdef fundus    'DRU Grid Type'              int8   "${admin}"   tag         tag        false      'DRU Grid Type'
modtagdef fundus    'Inc Pignment'               int8   "${admin}"   tag         tag        false      'Inc Pigment'
modtagdef fundus    'RPE Depigment'              int8   "${admin}"   tag         tag        false      'RPE Depigment'
modtagdef fundus    '# RPE Depigment Subfields'  int8   "${admin}"   tag         tag        false      '# 0-9'

modtagdef fundus    'Inc Pigment CC/CPT'         int8   "${admin}"   tag         tag        false      'Inc/RPE Lesions'
modtagdef fundus    'RPE Depigment CC/CPT'       int8   "${admin}"   tag         tag        false      'Inc/RPE Lesions'

modtagdef fundus    'Geographic Atrophy'         int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'PED/RD'                     int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'SubRet Hem'                 int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'SubRet Scar'                int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'ARM RX'                     int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'Lesions Summary'            int8   "${admin}"   tag         tag        false      'no/yes/CG'

modtagdef fundus    'GA # DAs in Grid'           int8   "${admin}"   tag         tag        false      '# 0-16'
modtagdef fundus    'Ex # DAs in Grid'           int8   "${admin}"   tag         tag        false      '# 0-16'

modtagdef fundus    'Calcified Drusen'           int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Peripheral Drusen'          int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Peripap Atrophy'            int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Art Sheathing'              int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Cen Art Occlus'             int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Br Art Occlus'              int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Cen Vein Occlus'            int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Br Vein Occlus'             int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Hollen Plaque'              int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Ast Hyalosis'               int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Nevus'                      int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Chorioret Scar'             int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'SWR Tension'                int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'SWR Cello Reflex'           int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Mac Hole'                   int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Histoplasmosis'             int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Ret Detach'                 int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Large C/D'                  int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Thick Vit/Glial'            int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Other (comments)'           int8   "${admin}"   tag         tag        false      'Other Lesions +PT'

modtagdef fundus    'Other Lesions Summary'      int8   "${admin}"   tag         tag        false      'no/yes'

modtagdef fundus    'Diabetic Retinopathy Level' int8   "${admin}"   tag         tag        false      'Diabetic Retinopathy Level'

tag "fundus brief tags" "_cfg_file list tags" tagname "Modality"
tag "fundus brief tags" "_cfg_file list tags" tagname "Lesions Summary"
tag "fundus brief tags" "_cfg_file list tags" tagname "Other Lesions Summary"
tag "fundus brief tags" "_cfg_file list tags" tagname "Diabetic Retinopathy Level"

tag "fundus brief tags" "_cfg_tag list tags" tagname "Modality"
tag "fundus brief tags" "_cfg_tag list tags" tagname "Lesions Summary"
tag "fundus brief tags" "_cfg_tag list tags" tagname "Other Lesions Summary"
tag "fundus brief tags" "_cfg_tag list tags" tagname "Diabetic Retinopathy Level"

EOF

chown ${SVCUSER}: /home/${SVCUSER}/dbsetup.sh
chmod a+x /home/${SVCUSER}/dbsetup.sh

# setup db tables
runuser -c "~${SVCUSER}/dbsetup.sh" - ${SVCUSER}

# register our service code
cat > /etc/httpd/conf.d/zz_${SVCPREFIX}.conf <<EOF
# this file must be loaded (alphabetically) after wsgi.conf

# need this for some of the RESTful URIs we can generate
AllowEncodedSlashes On

WSGIDaemonProcess ${SVCPREFIX} processes=4 threads=15 user=${SVCUSER}

WSGIScriptAlias /${SVCPREFIX} ${TAGFILERDIR}/wsgi/tagfiler.wsgi

WSGISocketPrefix ${RUNDIR}/wsgi
WSGIChunkedRequest On

Alias /${SVCPREFIX}/static /var/www/html/${SVCPREFIX}/static

<Location /${SVCPREFIX}>

    WSGIProcessGroup ${SVCPREFIX}
    
    # AuthType Digest
    # AuthName "${SVCPREFIX}"
    # AuthDigestDomain /${SVCPREFIX}/
    # AuthUserFile /etc/httpd/passwd/passwd
    # Require valid-user

</Location>

<Location /${SVCPREFIX}/static>

   # we don't want authentication on the applet download etc.
   Satisfy Any
   Allow from all

</Location>

<Directory ${TAGFILERDIR}/wsgi>

#    SetEnv ${SVCPREFIX}.dbnstr postgres
#    SetEnv ${SVCPREFIX}.dbstr  ${SVCUSER}

     # All other settings are tagged on dataset 'tagfiler configuration' now

</Directory>

EOF

signedjar=signed-isi-misd-tagfiler-upload-applet.jar
namespace=edu/isi/misd/tagfiler/util
props=tagfiler.properties


if [[ -n "$APPLETBUILD" ]] \
    && [[ -f "${APPLETBUILD}/lib/${signedjar}" ]] \
    && [[ -f "${APPLETBUILD}/src/${namespace}/${props}" ]]
then
    mkdir -p /var/www/html/${SVCPREFIX}/static/${namespace}/
    cp "${APPLETBUILD}/lib/${signedjar}" ${deploydir}
    cp "${APPLETBUILD}/src/${namespace}/${props}" ${deploydir}/${namespace}/
else
    cat <<EOF
Integration notes
-------------------------

Could not find one of:
   "${APPLETBUILD}/lib/${signedjar}"
   "${APPLETBUILD}/src/${namespace}/${props}"

You need to build a signed jar and do this manually:

cp signed-isi-misd-tagfiler-upload-applet.jar \
   /var/www/html/${SVCPREFIX}/static/

cp tagfiler.properties \
   /var/www/html/${SVCPREFIX}/static/edu/isi/misd/tagfiler/util

chmod -R a+r /var/www/html/${SVCPREFIX}/static/*
chmod -R a+r ${deploydir}

EOF
fi

if [[ -d /etc/logrotate.d/ ]]
then
    cat > /etc/logrotate.d/${SVCPREFIX} <<EOF
/var/www/${SVCPREFIX}-logs/messages {
    missingok
    dateext
    create 0600 tagfiler tagfiler
    daily
    minsize 500k
    maxage 30
    ifempty
    sharedscripts
    postrotate
        /sbin/service httpd reload > /dev/null 2>/dev/null || true
    endscript
}
EOF
fi

