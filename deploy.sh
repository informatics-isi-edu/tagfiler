#!/bin/sh

######
# NOTE: you can leave all this as defaults and modify Makefile
# which invokes this with SVCPREFIX...
######

# this is the URL base path of the service
SVCPREFIX=${1:-tagfiler}

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

# we need all of this
yum -y install httpd mod_wsgi \
    postgresql{,-devel,-server} \
    python{,-psycopg2,-webpy,-ply}

# let's try this blindly in case we need it
service postgresql initdb

# set the services to run automatically?
chkconfig httpd on
chkconfig postgresql on

# finish initializing system for our service
mkdir -p ${SVCDIR}/templates
mkdir -p ${DATADIR}
mkdir -p ${RUNDIR}

if ! runuser -c "/bin/true" ${SVCUSER}
then
    useradd -m -r ${SVCUSER}
fi

chown ${SVCUSER}: ${DATADIR}
chmod og=rx ${DATADIR}

# try some blind database setup as well
service postgresql start
runuser -c "createuser -S -D -R ${SVCUSER}" - ${PGADMIN}
runuser -c "createdb ${SVCUSER}" - ${PGADMIN}


# create local helper scripts
mkdir /etc/httpd/passwd

cat > ${HOME}/README-${SVCPREFIX} <<EOF
This service requires passwords to be configured via:

  htdigest /etc/httpd/passwd/passwd "${SVCUSER}" username

for each user you wish to add.

EOF

cat > /home/${SVCUSER}/dbsetup.sh <<EOF
#!/bin/sh

# this script will recreate all tables, but only on a clean database

psql -c "CREATE TABLE files ( name text PRIMARY KEY )"
psql -c "CREATE TABLE fileversions ( name text REFERENCES files (name) ON DELETE CASCADE, version int NOT NULL, UNIQUE (name, version) )"
psql -c "CREATE TABLE tagdefs ( tagname text PRIMARY KEY, typestr text )"
psql -c "CREATE TABLE filetags ( file text REFERENCES files (name) ON DELETE CASCADE, tagname text REFERENCES tagdefs (tagname) ON DELETE CASCADE, UNIQUE (file, tagname) )"

EOF

chown ${SVCUSER}: /home/${SVCUSER}/dbsetup.sh
chmod a+x /home/${SVCUSER}/dbsetup.sh

cat > /home/${SVCUSER}/dbclear.sh <<EOF
#!/bin/sh

# this script will remove all service tables to clean the database

psql -c "SELECT tagname FROM tagdefs" -t | while read tagname
do
   psql -c "DROP TABLE \"${tagname}\""
done

psql -c "DROP TABLE filetags"
psql -c "DROP TABLE tagdefs"
psql -c "DROP TABLE fileversions"
psql -c "DROP TABLE files"

EOF

chown ${SVCUSER}: /home/${SVCUSER}/dbclear.sh
chmod a+x /home/${SVCUSER}/dbclear.sh

# blindly clean and setup db tables
runuser -c "~${SVCUSER}/dbclear.sh" - ${SVCUSER}
runuser -c "~${SVCUSER}/dbsetup.sh" - ${SVCUSER}

# register our service code
cat > /etc/httpd/conf.d/zz_${SVCPREFIX}.conf <<EOF
# this file must be loaded (alphabetically) after wsgi.conf

# need this for some of the RESTful URIs we can generate
AllowEncodedSlashes On

WSGIDaemonProcess ${SVCPREFIX} processes=4 threads=15 user=${SVCUSER}

WSGIScriptAlias /${SVCPREFIX} ${SVCDIR}/dataserv.wsgi

WSGISocketPrefix ${RUNDIR}/wsgi

<Directory ${SVCDIR}>

    WSGIProcessGroup ${SVCPREFIX}

    SetEnv ${SVCPREFIX}.source_path ${SVCDIR}
    SetEnv ${SVCPREFIX}.dbnstr postgres
    SetEnv ${SVCPREFIX}.dbstr ${SVCUSER}
    SetEnv ${SVCPREFIX}.home http://${HOME_HOST}
    SetEnv ${SVCPREFIX}.store_path ${DATADIR}
    SetEnv ${SVCPREFIX}.template_path ${SVCDIR}/templates
    SetEnv ${SVCPREFIX}.chunkbytes 1048576

    AuthType Digest
    AuthName "${SVCPREFIX}"
    AuthDigestDomain /${SVCPREFIX}/
    AuthUserFile /etc/httpd/passwd/passwd
    Require valid-user

</Directory>

EOF

