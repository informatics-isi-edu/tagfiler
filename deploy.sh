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
chown ${SVCUSER}: ${LOGDIR}

if ! runuser -c "/bin/true" ${SVCUSER}
then
    useradd -m -r ${SVCUSER}
fi

chown ${SVCUSER}: ${DATADIR}
chmod og=rx ${DATADIR}

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
      psql -c "CREATE TABLE \\"_\$1\\" ( file text REFERENCES files (name) ON DELETE CASCADE, value \$2, UNIQUE(file, value) )"
      psql -c "CREATE INDEX \\"_\$1_value_idx\\" ON \\"_\$1\\" (value)"
   else
      psql -c "CREATE TABLE \\"_\$1\\" ( file text PRIMARY KEY REFERENCES files (name) ON DELETE CASCADE )"
   fi
}

#      TAGNAME        TYPE        OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR
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
      "INSERT INTO tag\${mode}ers (tagname, value) VALUES ('\$tag', '\$1')"
      shift
   done
}

tag()
{
   # args: file tag typestr [value]
   if [[ -n "\$3" ]]
   then
      psql -c "INSERT INTO \\"_\$2\\" ( file, value ) VALUES ( '\$1', '\$4' )"
   else
      psql -c "INSERT INTO \\"_\$2\\" ( file ) VALUES ( '\$1' )"
   fi
   if [[ -z "\$(psql -A -t -c "SELECT * FROM \\"_\$2\\" WHERE file = '\$1'")" ]]
   then
      psql -c "INSERT INTO filetags (file, tagname) VALUES ('\$1', '\$2')"
   fi
}

# pre-established stored queries for use case
storedquery()
{
   # args: name terms owner [readuser]...
   psql -c "INSERT INTO files (name, local, location) VALUES ( '\$1', False, 'https://${HOME_HOST}/${SVCPREFIX}/query/\$2' )"
   tag "\$1" owner text "\$3"
   tag "\$1" "list on homepage"
   file=\$1
   shift 3
   while [[ \$# -gt 0 ]]
   do
      tag "\$file" "read users" text "\$1"
      shift
   done
}

storedquery "New image studies" "Image%20Set;Downloaded:not:" admin admin
storedquery "Previous image studies" "Image%20Set;Downloaded" admin admin
storedquery "All image studies" "Image%20Set" admin admin

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

    SetEnv ${SVCPREFIX}.help https://confluence.misd.isi.edu:8443/display/DEIIMGUP/Home
    SetEnv ${SVCPREFIX}.jira https://jira.misd.isi.edu:8444/browse/DEIIMGUP
#    SetEnv ${SVCPREFIX}.policyrules uploader,dirc,true,false;accessioner,dirc,true,true;grader,dirc,true,false
    SetEnv tagfiler.filelisttags 'Image%20Set,bytes,owner,read%20users,write%20users'
    SetEnv tagfiler.filelisttagswrite 'read%20users,write%20users'
    SetEnv tagfiler.customtags 'Image Type,Capture Date,Comment'
    SetEnv tagfiler.requiredtags 'Image Type,Capture Date'
#    SetEnv ${SVCPREFIX}.localFilesImmutable true
#    SetEnv tagfiler.appletTest /home/userid/appletTest.properties
#    SetEnv tagfiler.appletlog /home/userid/applet.log
#    SetEnv ${SVCPREFIX}.home https://${HOME_HOST}
    SetEnv ${SVCPREFIX}.webauthnhome https://${HOME_HOST}/webauthn
    SetEnv ${SVCPREFIX}.webauthnrequire Yes
#    SetEnv ${SVCPREFIX}.store_path ${DATADIR}
#    SetEnv ${SVCPREFIX}.log_path ${LOGDIR}
#    SetEnv ${SVCPREFIX}.template_path ${TAGFILERDIR}/templates
#    SetEnv ${SVCPREFIX}.chunkbytes 1048576
#    SetEnv ${SVCPREFIX}.webauthnexpiremins 10
#    SetEnv ${SVCPREFIX}.webauthnrotatemins 120
    SetEnv ${SVCPREFIX}.subtitle 'Tagfiler (trunk) on ${HOME_HOST}'
    SetEnv ${SVCPREFIX}.logo '<img alt="tagfiler" title="Tagfiler (trunk)" src="/${SVCPREFIX}/static/logo.png" width="245" height="167" />'
    SetEnv ${SVCPREFIX}.contact '<p>Your HTML here</p>'

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

