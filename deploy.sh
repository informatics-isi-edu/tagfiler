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

psql -c "CREATE TABLE files ( name text PRIMARY KEY, local boolean default False, location text )"
psql -c "CREATE TABLE tagdefs ( tagname text PRIMARY KEY, typestr text, multivalue boolean, readpolicy text, writepolicy text, owner text )"
psql -c "CREATE TABLE tagreaders ( tagname text REFERENCES tagdefs ON DELETE CASCADE, value text NOT NULL, UNIQUE(tagname, value) )"
psql -c "CREATE TABLE tagwriters ( tagname text REFERENCES tagdefs ON DELETE CASCADE, value text NOT NULL, UNIQUE(tagname, value) )"
psql -c "CREATE TABLE filetags ( file text REFERENCES files (name) ON DELETE CASCADE, tagname text REFERENCES tagdefs (tagname) ON DELETE CASCADE, UNIQUE (file, tagname) )"

psql -c "CREATE SEQUENCE transmitnumber"

# pre-establish core restricted tags used by codebase
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

   if [[ -n "\$3" ]]
   then
      psql -c "INSERT INTO tagdefs ( tagname, typestr, owner, readpolicy, writepolicy, multivalue ) VALUES ( '\$1', '\${7:-\${2}}', '\$3', '\$4', '\$5', \$6 )"
   else
      psql -c "INSERT INTO tagdefs ( tagname, typestr, readpolicy, writepolicy, multivalue ) VALUES ( '\$1', '\${7:-\${2}}', '\$4', '\$5', \$6 )"
   fi
   if [[ -n "\$2" ]]
   then
      if [[ "\$2" = "text" ]]
      then
         default="DEFAULT ''"
      else
         default=""
      fi
      psql -c "CREATE TABLE \\"_\$1\\" ( file text REFERENCES files (name) ON DELETE CASCADE, value \$2 \${default}, UNIQUE(file, value) )"
      psql -c "CREATE INDEX \\"_\$1_value_idx\\" ON \\"_\$1\\" (value)"
   else
      psql -c "CREATE TABLE \\"_\$1\\" ( file text PRIMARY KEY REFERENCES files (name) ON DELETE CASCADE )"
   fi
}

cfgtagdef()
{
   tagname="_cfg_\$1"
   shift
   tagdef "\$tagname" "\$@"
}


#         TAGNAME       TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR

cfgtagdef home          text        ""      file        file       false
cfgtagdef 'webauthn home' text      ""      file        file       false
cfgtagdef 'webauthn require' text   ""      file        file       false
cfgtagdef 'store path'  text        ""      file        file       false
cfgtagdef 'log path'    text        ""      file        file       false
cfgtagdef 'template path' text      ""      file        file       false
cfgtagdef 'chunk bytes' text        ""      file        file       false
cfgtagdef 'tag list tags' text      ""      file        file       true       tagname
cfgtagdef 'file list tags' text     ""      file        file       true       tagname
cfgtagdef 'file list tags write' text ""    file        file       true       tagname
cfgtagdef 'applet tags' text        ""      file        file       true       tagname
cfgtagdef 'applet tags require' text ""     file        file       true       tagname
cfgtagdef 'applet properties' text  ""      file        file       false
cfgtagdef 'local files immutable' text ""   file        file       false
cfgtagdef 'remote files immutable' text ""  file        file       false
cfgtagdef 'policy remappings' text  ""      file        file       true
cfgtagdef 'applet test log' text    ""      file        file       false
cfgtagdef 'applet test properties' text ""  file        file       true
cfgtagdef subtitle      text        ""      file        file       false
cfgtagdef logo          text        ""      file        file       false
cfgtagdef contact       text        ""      file        file       false
cfgtagdef help          text        ""      file        file       false
cfgtagdef bugs          text        ""      file        file       false
cfgtagdef 'connections' text        ""      tag         tag        false
cfgtagdef 'upload chunks' text        ""      tag         tag        false
cfgtagdef 'download chunks' text        ""      tag         tag        false
cfgtagdef 'socket buffer size' text        ""      tag         tag        false
cfgtagdef 'applet chunk bytes' text        ""      tag         tag        false

#      TAGNAME        TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR

tagdef '_type_name'   text        ""      file        file       false
tagdef '_type_description' text   ""      file        file       false
tagdef '_type_dbtype' text        ""      file        file       false
tagdef '_type_values' text        ""      file        file       true

tagdef owner          text        ""      anonymous   fowner     false      role
tagdef created        timestamptz ""      anonymous   system     false
tagdef "read users"   text        ""      anonymous   fowner     true       role
tagdef "write users"  text        ""      anonymous   fowner     true       role
tagdef "modified by"  text        ""      anonymous   system     false      role
tagdef modified       timestamptz ""      anonymous   system     false
tagdef bytes          int8        ""      anonymous   system     false
tagdef name           text        ""      anonymous   system     false
tagdef url            text        ""      anonymous   system     false
tagdef content-type   text        ""      anonymous   file       false
tagdef sha256sum      text        ""      file        file       false

tagdef "Transmission Number" \
                      int8        ""    file        file       false

tagdef "list on homepage" ""      "admin"   anonymous   tag        false
tagdef "Image Set"    ""          "admin"   file        file       false

tagacl()
{
   # args: tagname {read|write} [value]...
   tag=\$1
   mode=\${2:0:4}
   shift 2
   while [[ \$# -gt 0 ]]
   do
      psql -c "INSERT INTO tag\${mode}ers (tagname, value) VALUES ('\$tag', '\$1')"
      shift
   done
}

tag()
{
   # args: file tag typestr [value]...
   # for non-empty typestr
   #     does one default value insert for 0 values
   #     does N value inserts for N>0 values

   file="\$1"
   tagname="\$2"
   typestr="\$3"

   shift 3

   if [[ -z "\$typestr" ]] || [[ \$# -eq 0 ]]
   then
      psql -c "INSERT INTO \\"_\$tagname\\" ( file ) VALUES ( '\$file' )"
   elif [[ \$# -gt 0 ]]
   then
      while [[ \$# -gt 0 ]]
      do
         psql -c "INSERT INTO \\"_\$tagname\\" ( file, value ) VALUES ( '\$file', '\$1' )"
         shift
      done
   fi

   # add to filetags only if this insert changes status
   if [[ -z "\$(psql -A -t -c "SELECT * FROM filetags WHERE file = '\$file' AND tagname = '\$tagname'")" ]] \
     && [[ -n "\$(psql -A -t -c "SELECT * FROM \\"_\$tagname\\" WHERE file = '\$file'")" ]]
   then
      psql -c "INSERT INTO filetags (file, tagname) VALUES ('\$file', '\$tagname')"
   fi
}

# pre-established stored queries for use case
storedquery()
{
   # args: name terms owner [readuser]...
   case \$2 in
      http:*|/*)
          url=\$2
          ;;
      *)
          url="https://${HOME_HOST}/${SVCPREFIX}/query/\$2"
          ;;
   esac

   psql -c "INSERT INTO files (name, local, location) VALUES ( '\$1', False, '\$url' )"
   tag "\$1" owner text "\$3"
   file=\$1
   shift 3
   while [[ \$# -gt 0 ]]
   do
      tag "\$file" "read users" text "\$1"
      shift
   done
}

storedquery "New image studies" "Image%20Set;Downloaded:not:" admin
storedquery "Previous image studies" "Image%20Set;Downloaded" admin
storedquery "All image studies" "Image%20Set" admin

for x in "New image studies" "Previous image studies" "All image studies"
do
   tag "\$x" "list on homepage"
done

storedquery "tagfiler configuration" "https://${HOME_HOST}/${SVCPREFIX}/tags/tagfiler%20configuration" admin "*"

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
typedef tagname      text          'Tag name'

cfgtag()
{
   tagname="_cfg_\$1"
   shift
   tag "tagfiler configuration" "\$tagname" "\$@"
}

#cfgtag "home" text 'https://${HOME_HOST}'
cfgtag "webauthn home" text 'https://${HOME_HOST}/webauthn'
#cfgtag "webauthn require" text 'True'

#cfgtag "store path" text '${DATADIR}'
#cfgtag "log path" text '${LOGDIR}'
#cfgtag "template path" text '${TAGFILERDIR}/templates'
#cfgtag "chunk bytes" text '1048576'

#cfgtag "connections" text '2'
#cfgtag "upload chunks" text 'true'
#cfgtag "download chunks" text 'true'
#cfgtag "socket buffer size" text '8192'
#cfgtag "applet chunk bytes" text '4194304'

cfgtag "file list tags" text 'Image Set' bytes owner 'read users' 'write users'
cfgtag "file list tags write" text 'read users' 'write users'
#cfgtag "applet tags" text ...
#cfgtag "applet tags require" text ...
#cfgtag "applet properties" text 'tagfiler.properties'

#cfgtag "local files immutable" text 'True'
#cfgtag "policy remappings" text 'uploader,dirc,true,false' 'accessioner,dirc,true,true' 'grader,dirc,true,false'

#cfgtag "applet test properties" text '/home/userid/appletTest.properties'
#cfgtag "applet test log" text '/home/userid/applet.log'

cfgtag "subtitle" text 'Tagfiler (trunk) on ${HOME_HOST}'
cfgtag "logo" text '<img alt="tagfiler" title="Tagfiler (trunk)" src="/${SVCPREFIX}/static/logo.png" width="245" height="167" />'
cfgtag "contact" text '<p>Your HTML here</p>'
cfgtag "help" text 'https://confluence.misd.isi.edu:8443/display/DEIIMGUP/Home'
cfgtag "bugs" text 'https://jira.misd.isi.edu:8444/browse/DEIIMGUP'

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

EOF
fi

chmod -R a+r ${deploydir}

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

