#!/bin/sh

# you can set this to override...
HOME_HOST=

# default to `hostname` setting
HOST=$(hostname)
HOME_HOST=${HOME_HOST:-$HOST}

# this is the privileged postgresql user for createdb etc.
PGADMIN=postgres

# this is the URL base path of the service
# service automatically detects how it is called
SVCPREFIX=tagfiler

# this is the service daemon account
SVCUSER=${SVCPREFIX}

SVCDIR=/var/www/${SVCPREFIX}
DATADIR=${SVCDIR}-data

# we need all of this
yum -y install httpd mod_wsgi \
    postgresql{,-devel,-server} \
    python{,-psycopg2,-webpy}

# let's try this blindly in case we need it
service postgresql initdb

# set the services to run automatically?
chkconfig httpd on
chkconfig postgresql on

# finish initializing system for our service
mkdir -p ${SVCDIR}/templates
mkdir -p ${DATADIR}

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

cat > /home/${SVCUSER}/dbsetup.sh <<EOF
#!/bin/sh

# this script will recreate all tables, but only on a clean database

psql -c "CREATE TABLE files ( name text PRIMARY KEY )"
psql -c "CREATE TABLE fileversions ( name text REFERENCES files (name), version int, UNIQUE (name, version) )"
psql -c "CREATE TABLE tagdefs ( tagname text PRIMARY KEY, typestr text )"
psql -c "CREATE TABLE filetags ( file text REFERENCES files (name), tagname text REFERENCES tagdefs (tagname), UNIQUE (file, tagname) )"

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

WSGIDaemonProcess ${SVCPREFIX} processes=4 threads=15 user=${SVCUSER}
WSGIProcessGroup ${SVCPREFIX}
WSGIScriptAlias /${SVCPREFIX} ${SVCDIR}/dataserv.wsgi

WSGISocketPrefix /var/run/wsgi/wsgi

<Directory ${SVCDIR}>
    SetEnv dataserv.source_path ${SVCDIR}
    SetEnv dataserv.dbnstr postgres
    SetEnv dataserv.dbstr ${SVCUSER}
    SetEnv dataserv.home http://${HOME_HOST}
    SetEnv dataserv.store_path ${DATADIR}
    SetEnv dataserv.template_path ${SVCDIR}/templates
    SetEnv dataserv.chunkbytes 1048576
    Order allow,deny
    Allow from all
</Directory>

EOF

