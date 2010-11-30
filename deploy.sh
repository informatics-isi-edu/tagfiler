#!/bin/sh

######
# NOTE: you can leave all this as defaults and modify Makefile
# which invokes this with SVCPREFIX...
######

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

psql -q -t -c "CREATE TABLE files ( name text PRIMARY KEY, local boolean default False, location text )"
psql -q -t -c "CREATE TABLE tagdefs ( tagname text PRIMARY KEY, typestr text, multivalue boolean, readpolicy text, writepolicy text, owner text )"
psql -q -t -c "CREATE TABLE tagreaders ( tagname text REFERENCES tagdefs ON DELETE CASCADE, value text NOT NULL, UNIQUE(tagname, value) )"
psql -q -t -c "CREATE TABLE tagwriters ( tagname text REFERENCES tagdefs ON DELETE CASCADE, value text NOT NULL, UNIQUE(tagname, value) )"
psql -q -t -c "CREATE TABLE filetags ( file text REFERENCES files (name) ON DELETE CASCADE, tagname text REFERENCES tagdefs (tagname) ON DELETE CASCADE, UNIQUE (file, tagname) )"

psql -q -t -c "CREATE SEQUENCE transmitnumber"

tagdef()
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

   if [[ -n "\$3" ]]
   then
      psql -q -t -c "INSERT INTO tagdefs ( tagname, typestr, owner, readpolicy, writepolicy, multivalue ) VALUES ( '\$1', '\${7:-\${2}}', '\$3', '\$4', '\$5', \$6 )"
   else
      psql -q -t -c "INSERT INTO tagdefs ( tagname, typestr, readpolicy, writepolicy, multivalue ) VALUES ( '\$1', '\${7:-\${2}}', '\$4', '\$5', \$6 )"
   fi
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
         fk="REFERENCES files (name) ON DELETE CASCADE"
      else
         fk=""
      fi
      psql -q -t -c "CREATE TABLE \\"_\$1\\" ( file text REFERENCES files (name) ON DELETE CASCADE, value \$2 \${default} \${fk}, UNIQUE(file, value) )"
      psql -q -t -c "CREATE INDEX \\"_\$1_value_idx\\" ON \\"_\$1\\" (value)"
   else
      psql -q -t -c "CREATE TABLE \\"_\$1\\" ( file text PRIMARY KEY REFERENCES files (name) ON DELETE CASCADE )"
   fi
}

#      TAGNAME        TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR

tagdef '_type_name'   text        ""      file        file       false
tagdef '_type_description' text   ""      file        file       false
tagdef '_type_dbtype' text        ""      file        file       false
tagdef '_type_values' text        ""      file        file       true

tagdef owner          text        ""      anonymous   fowner     false      role
tagdef created        timestamptz ""      anonymous   system     false
tagdef "read users"   text        ""      anonymous   fowner     true       rolepat
tagdef "write users"  text        ""      anonymous   fowner     true       rolepat
tagdef "modified by"  text        ""      anonymous   system     false      role
tagdef modified       timestamptz ""      anonymous   system     false
tagdef bytes          int8        ""      anonymous   system     false
tagdef name           text        ""      anonymous   system     false
tagdef url            text        ""      file        file       false      url
tagdef content-type   text        ""      anonymous   file       false
tagdef sha256sum      text        ""      file        file       false

tagdef contains       text        ""      file        file       true       file
tagdef version        text        ""      file        file       true       file
tagdef "version number" int8      ""      file        system     false
tagdef "Version Set"  ""          ""      file        system     false

tagdef "Transmission Number" \
                      int8        ""    file        file       false

tagdef "list on homepage" ""      ""      anonymous   tag        false
tagdef "Image Set"    ""          "admin"   file        file       false

tagacl()
{
   # args: tagname {read|write} [value]...
   local tag=\$1
   local mode=\${2:0:4}
   shift 2
   while [[ \$# -gt 0 ]]
   do
      psql -q -t -c "INSERT INTO tag\${mode}ers (tagname, value) VALUES ('\$tag', '\$1')"
      shift
   done
}

tagacl "list on homepage" read "*"
tagacl "list on homepage" write "admin"

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
      psql -q -t -c "INSERT INTO \\"_\$tagname\\" ( file ) VALUES ( '\$file' )"
   elif [[ \$# -gt 0 ]]
   then
      while [[ \$# -gt 0 ]]
      do
         psql -q -t -c "INSERT INTO \\"_\$tagname\\" ( file, value ) VALUES ( '\$file', '\$1' )"
         shift
      done
   fi

   # add to filetags only if this insert changes status
   if [[ -z "\$(psql -A -t -c "SELECT * FROM filetags WHERE file = '\$file' AND tagname = '\$tagname'")" ]] \
     && [[ -n "\$(psql -A -t -c "SELECT * FROM \\"_\$tagname\\" WHERE file = '\$file'")" ]]
   then
      psql -q -t -c "INSERT INTO filetags (file, tagname) VALUES ('\$file', '\$tagname')"
   fi
}

# pre-established stored queries for use case
storedquery()
{
   # args: name terms owner [readuser]...
   local file="\$1"
   local url="\$2"
   local owner="\$3"
   shift 3

   case "\$url" in
      http*:*|/*)
          url="\$url"
          ;;
      *)
          url="https://${HOME_HOST}/${SVCPREFIX}/query/\$url"
          ;;
   esac

   echo "create stored query: '\$file' --> '\$url'..."
   psql -t -q -c "INSERT INTO files (name, local, location) VALUES ( '\$file', False, '\$url' )"
   tag "\$file" name text "\$file"
   tag "\$file" url text "\$url"
   tag "\$file" owner text "\$owner"
   while [[ \$# -gt 0 ]]
   do
      tag "\$file" "read users" text "\$1"
      shift
   done
}

storedquery "New image studies" 'Image%20Set;Downloaded:not:?view=study%20tags' admin downloader
storedquery "Previous image studies" 'Image%20Set;Downloaded?view=study%20tags' admin downloader
storedquery "All image studies" 'Image%20Set?view=study%20tags' admin downloader

for x in "New image studies" "Previous image studies" "All image studies"
do
   tag "\$x" "list on homepage"
done

storedquery "tagfiler configuration" "https://${HOME_HOST}/${SVCPREFIX}/tags/tagfiler%20configuration?view=configuration%20tags" admin "*"

typedef()
{
   typename="\$1"
   dbtype="\$2"
   desc="\$3"
   shift 3
   storedquery "_type_def_\${typename}" "https://${HOME_HOST}/${SVCPREFIX}/tags/tagfiler%20configuration" admin "*"
   tag "_type_def_\${typename}" "_type_name" text "\${typename}"
   tag "_type_def_\${typename}" "_type_dbtype" text "\${dbtype}"
   tag "_type_def_\${typename}" "_type_description" text "\${desc}"
   if [[ \$# -gt 0 ]]
   then
      tag "_type_def_\${typename}" "_type_values" text "\$@"
   fi
}

typedef ''           ''            'No content'
typedef int8         int8          'Integer'
typedef float8       float8        'Floating point'
typedef date         date          'Date'
typedef timestamptz  timestamptz   'Date and time with timezone'
typedef text         text          'Text'
typedef role         text          'Role'
typedef rolepat      text          'Role pattern'
typedef tagname      text          'Tag name'
typedef url          text          'URL'
typedef file         text          'Dataset'

storedquery "configuration tags" "https://${HOME_HOST}/${SVCPREFIX}/tags/configuration%20tags" admin "*"

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
cfgtagdef 'use versions' 'text'     ""      file        file       false
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

cfgtag "file list tags" text bytes owner 'read users' 'write users'
#cfgtag "file list tags write" text 'read users' 'write users'
#cfgtag "applet tags" text ...
#cfgtag "applet tags require" text ...
#cfgtag "applet properties" text 'tagfiler.properties'

#cfgtag "local files immutable" text 'True'
#cfgtag "remote files immutable" text 'True'

# remapping rules:
#  srcrole ; dstrole ; reader, ... ; writer, ...
# semi-colons required but readers and writers optional, e.g. srcrole;dstrole;;
cfgtag "policy remappings" text 'uploader;coordinator;uploader,downloader;uploader'

#cfgtag "applet test properties" text '/home/userid/appletTest.properties'
#cfgtag "applet test log" text '/home/userid/applet.log'

cfgtag "subtitle" text 'Tagfiler (trunk) on ${HOME_HOST}'
cfgtag "logo" text '<img alt="tagfiler" title="Tagfiler (trunk)" src="/${SVCPREFIX}/static/logo.png" width="245" height="167" />'
cfgtag "contact" text '<p>Your HTML here</p>'
cfgtag "help" text 'https://confluence.misd.isi.edu:8443/display/DEIIMGUP/Home'
cfgtag "bugs" text 'https://jira.misd.isi.edu/browse/DEIIMGUP'


## Types and Tags for NEI MISD/DEI demo...

tagdef "Downloaded"   ""          ""      tag         tag        false
tagacl "Downloaded" read downloader
tagacl "Downloaded" write downloader

storedquery "study tags" "https://${HOME_HOST}/${SVCPREFIX}/tags/study%20tags" admin "*"
storedquery "fundus tags" "https://${HOME_HOST}/${SVCPREFIX}/tags/fundus%20tags" admin "*"
storedquery "fundus brief tags" "https://${HOME_HOST}/${SVCPREFIX}/tags/fundus%20brief%20tags" admin "*"

modtagdef()
{
   local modality="\$1"
   local tagname="\$2"
   shift 2
   tagdef "\$tagname" "\$@"
   tag "\$modality tags" "_cfg_file list tags" tagname "\$tagname"
   tag "\$modality tags" "_cfg_tag list tags" tagname "\$tagname"
   tagacl "\$tagname" read downloader
   tagacl "\$tagname" write grader
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
tagdef   Modality                     text   admin   tag         tag        false      Modality
tag "fundus tags" "_cfg_file list tags" tagname "Modality"

tagdef   'Study Name'                 text   admin   tag         tag        false      'Study Name'
tagdef   'Study Participant'          text   admin   tag         tag        false
tagdef   'Study Date'                 date   admin   tag         tag        false

for tag in 'Modality' 'Study Name' 'Study Participant' 'Study Date'
do
   tagacl "\$tag" read PI downloader
   tagacl "\$tag" write tagger coordinator
done

# set default applet tags and configure named views too...
cfgtag "applet tags" tagname  "Modality" "Study Name" "Study Participant" "Study Date"
cfgtag "applet tags require" tagname  "Modality" "Study Name" "Study Participant" "Study Date"

for tag in '_cfg_file list tags' '_cfg_file list tags write' '_cfg_applet tags' '_cfg_applet tags require'
do 
   tag 'study tags' "\$tag" tagname "Modality" "Study Name" "Study Participant" "Study Date"
done


#         MOD    TAGNAME                      TYPE   OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR
modtagdef fundus    'Max DRU Size'               int8   admin   tag         tag        false      'Max DRU Size'
modtagdef fundus    '# DRU Size Subfields'       int8   admin   tag         tag        false      '# 0-9'
modtagdef fundus    'DRU Area'                   int8   admin   tag         tag        false      'DRU Area'
modtagdef fundus    'Max DRU Type'               int8   admin   tag         tag        false      'Max DRU Type'
modtagdef fundus    '# DRU Type Subfields'       int8   admin   tag         tag        false      '# 0-9'
modtagdef fundus    'DRU Grid Type'              int8   admin   tag         tag        false      'DRU Grid Type'
modtagdef fundus    'Inc Pignment'               int8   admin   tag         tag        false      'Inc Pigment'
modtagdef fundus    'RPE Depigment'              int8   admin   tag         tag        false      'RPE Depigment'
modtagdef fundus    '# RPE Depigment Subfields'  int8   admin   tag         tag        false      '# 0-9'

modtagdef fundus    'Inc Pigment CC/CPT'         int8   admin   tag         tag        false      'Inc/RPE Lesions'
modtagdef fundus    'RPE Depigment CC/CPT'       int8   admin   tag         tag        false      'Inc/RPE Lesions'

modtagdef fundus    'Geographic Atrophy'         int8   admin   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'PED/RD'                     int8   admin   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'SubRet Hem'                 int8   admin   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'SubRet Scar'                int8   admin   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'ARM RX'                     int8   admin   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'Lesions Summary'            int8   admin   tag         tag        false      'no/yes/CG'

modtagdef fundus    'GA # DAs in Grid'           int8   admin   tag         tag        false      '# 0-16'
modtagdef fundus    'Ex # DAs in Grid'           int8   admin   tag         tag        false      '# 0-16'

modtagdef fundus    'Calcified Drusen'           int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Peripheral Drusen'          int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Peripap Atrophy'            int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Art Sheathing'              int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Cen Art Occlus'             int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Br Art Occlus'              int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Cen Vein Occlus'            int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Br Vein Occlus'             int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Hollen Plaque'              int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Ast Hyalosis'               int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Nevus'                      int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Chorioret Scar'             int8   admin   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'SWR Tension'                int8   admin   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'SWR Cello Reflex'           int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Mac Hole'                   int8   admin   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Histoplasmosis'             int8   admin   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Ret Detach'                 int8   admin   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Large C/D'                  int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Thick Vit/Glial'            int8   admin   tag         tag        false      'Other Lesions'
modtagdef fundus    'Other (comments)'           int8   admin   tag         tag        false      'Other Lesions +PT'

modtagdef fundus    'Other Lesions Summary'      int8   admin   tag         tag        false      'no/yes'

modtagdef fundus    'Diabetic Retinopathy Level' int8   admin   tag         tag        false      'Diabetic Retinopathy Level'

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

cat > /home/${SVCUSER}/dbclear.sh <<EOF
#!/bin/sh

# this script will remove all service tables to clean the database

psql -c "SELECT tagname FROM tagdefs" -t | while read tagname
do
   psql -c "DROP TABLE \"_\${tagname//\"/\"\"}\""
done

psql -c "DROP TABLE filetags"
psql -c "DROP TABLE tagdefs"
psql -c "DROP TABLE files"

EOF

chown ${SVCUSER}: /home/${SVCUSER}/dbclear.sh
chmod a+x /home/${SVCUSER}/dbclear.sh

cat > /home/${SVCUSER}/dbdump.sh <<EOF
#!/bin/sh

# this script will remove all service tables to clean the database

psql -c "SELECT tagname FROM tagdefs" -t | while read tagname
do
    if [[ -n "\$tagname" ]]
    then
        echo "DUMPING TAG \"\${tagname}\""
        psql -c "SELECT * FROM \"_\${tagname//\"/\"\"}\""
    fi
done

for table in filetags tagdefs files
do
    echo "DUMPING TABLE \"\$table\""
    psql -c "SELECT * FROM \$table"
done
EOF

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

