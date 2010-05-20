#!/bin/sh

# this is the service daemon account
# change here and in dataserv_app.Application constructor!
SVCUSER=kczweb1

# this is the privileged postgresql user
PGADMIN=postgres

# this is the URL base path of the service
# service automatically detects how it is called
SVCPREFIX=dataserv

# these don't need to match SVCPREFIX
SVCDIR=dataserv  # also change in dataserv.wsgi
DATADIR=dataserv-data # also change in dataserv_app.Application

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
mkdir -p /var/www/${SVCDIR}/templates
mkdir -p /var/www/${DATADIR}
useradd -m -r ${SVCUSER}
chown ${SVCUSER}: /var/www/${DATADIR}
chmod og=rx /var/www/${DATADIR}
service postgres start
runuser -c "createuser -S -D -R ${SVCUSER}" ${PGADMIN}
runuser -c "createdb ${SVCUSER}" ${PGADMIN}

# create helper scripts

cat ~${SVCUSER}/dbsetup.sh <<EOF
#!/bin/sh

# this script will recreate all tables, but only on a clean database

psql -c "CREATE TABLE files ( name text PRIMARY KEY )"
psql -c "CREATE TABLE fileversions ( name text REFERENCES files (name), version int, UNIQUE (name, version) )"
psql -c "CREATE TABLE tagdefs ( tagname text PRIMARY KEY, typestr str )"
psql -c "CREATE TABLE filetags ( file text REFERENCES files (name), tagname text REFERENCES tagdefs (tagname), UNIQUE (file, tagname) )"

EOF

cat ~${SVCUSER}/dbclear.sh <<EOF
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

# run helper
runuser -c "~/dbsetup.sh" ${SVCUSER}

# register our service code
cat > /etc/httpd/conf.d/zz_dataserv.conf <<EOF
# this file must be loaded (alphabetically) after wsgi.conf

WSGIDaemonProcess dataserv processes=4 threads=15 user=${SVCUSER}
WSGIProcessGroup dataserv
WSGIScriptAlias /${SVCPREFIX} /var/www/${SVCDIR}/dataserv.wsgi
WSGISocketPrefix /var/run/wsgi/wsgi

<Directory /var/www/dataserv>
    Order allow,deny
    Allow from all
</Directory>

EOF

