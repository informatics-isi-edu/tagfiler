#!/bin/bash

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

######
# NOTE: you can leave all this as defaults and modify Makefile
# which invokes this with SVCPREFIX...
######

# role mapping used in default data and ACLs
admin="${admin:-admin}"

TAGFILERDIR=`python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()'`/tagfiler

# this is the URL base path of the service
SVCPREFIX=${1:-tagfiler}

# the core and template database names
DBNAME=${SVCPREFIX}
TEMPLATE=${SVCPREFIX}_template

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

# set the services to run automatically?
chkconfig httpd on

SVCHOME=$(eval "echo ~${SVCUSER}")

# Sets PostgreSQL database flags
#   $1 : db name
#   $2 : true/false flag for 'datistemplate'
#   $3 : true/false flag for 'datallowconn'
#
# A pg database cannot be deleted if its datistemplate flag is set to true. A 
# pg database cannot allow connections (open sessions) if its datallowconn 
# flag is set to false.
pg_set_db_flags()
{
  dbn=$1
  istempl=$2
  allowconn=$3

  echo "Updating pg_database flags for ${dbn} (template=${istempl}, allowconn=${allowconn})..."

  runuser -c "psql ${PGADMIN}" - ${PGADMIN} >/dev/null <<EOF
  UPDATE pg_database SET datistemplate='${istempl}', datallowconn='${allowconn}' WHERE datname='${dbn}';
EOF
}

# finish initializing system for our service
semanage fcontext --add --ftype "" --type httpd_sys_rw_content_t "${DATADIR}(/.*)?" \
    || semanage fcontext --add --ftype "" --type httpd_sys_script_rw_t "${DATADIR}(/.*)?"
mkdir -p ${DATADIR}
restorecon -rvF ${DATADIR}

mkdir -p ${RUNDIR}


if ! runuser -c "/bin/true" ${SVCUSER}
then
    useradd -m -r ${SVCUSER}
fi

# allow httpd/mod_wsgi based daemon process to access its homedir

semanage fcontext --add --ftype -- --type httpd_sys_content_t "${SVCHOME}/tagfiler-config\.json"

semanage fcontext --add --ftype -d --type httpd_sys_rw_content_t "${SVCHOME}" \
    || semanage fcontext --add --ftype -d --type httpd_sys_script_rw_t "${SVCHOME}"

semanage fcontext --add --ftype -- --type httpd_sys_rw_content_t "${SVCHOME}/[^/]+tab\.py" \
    || semanage fcontext --add --ftype -- --type httpd_sys_script_rw_t "${SVCHOME}/[^/]+tab\.py"

restorecon -rvF "${SVCHOME}"

chown ${SVCUSER}: ${DATADIR}
chmod og=rx ${DATADIR}

if runuser -c "psql -c 'select * from pg_user' ${PGADMIN}" - ${PGADMIN} | grep ${SVCUSER} 1>/dev/null
then
    :
else
	runuser -c "createuser -S -d -R ${SVCUSER}" - ${PGADMIN}
fi

# drop tagfiler_i databases
catalog_ids=$(runuser -c "psql -A -t -c 'select id from catalogs'" - ${SVCUSER} 2> /dev/null)
for id in $catalog_ids; do
  runuser -c "dropdb ${SVCPREFIX}_${id}" - ${SVCUSER}
done

# unset template flags
pg_set_db_flags ${TEMPLATE} false true

# create catalog and template databases
runuser -c "dropdb ${DBNAME}" - ${PGADMIN}
runuser -c "createdb -O ${SVCUSER} ${DBNAME}" - ${PGADMIN}
runuser -c "dropdb \"${TEMPLATE}\"" - ${PGADMIN}
runuser -c "createdb -O ${SVCUSER} \"${TEMPLATE}\"" - ${PGADMIN}

# create local helper scripts
mkdir -p /etc/httpd/passwd

backup()
{
    if [[ -f "$1" ]]
    then
	mv "$1" "$1".$(date +%Y%m%d_%H%M%S)
    fi
}

backup ${SVCHOME}/tagfiler-config.json
sed -e "s/svcuser/$SVCUSER/g" -e "s/adminrole/$admin/g" tagfiler-config.json > ${SVCHOME}/tagfiler-config.json
chown ${SVCUSER}: ${SVCHOME}/tagfiler-config.json
chmod ug=r,o= ${SVCHOME}/tagfiler-config.json

# copy database setup scripts to service user home
cp bin/dbsetup.sh ${SVCHOME}/dbsetup.sh
chown ${SVCUSER}: ${SVCHOME}/dbsetup.sh
chmod a+x ${SVCHOME}/dbsetup.sh

cp bin/dbsetup-template.sh ${SVCHOME}/dbsetup-template.sh
chown ${SVCUSER}: ${SVCHOME}/dbsetup-template.sh
chmod a+x ${SVCHOME}/dbsetup-template.sh

# setup core and template databases
runuser -c "${SVCHOME}/dbsetup.sh \"${DBNAME}\"" - ${SVCUSER}
runuser -c "${SVCHOME}/dbsetup-template.sh ${HOME_HOST} ${SVCPREFIX} \"${TEMPLATE}\" \"${admin}\"" - ${SVCUSER}

# set template flags
pg_set_db_flags ${TEMPLATE} true false

# register our service code
cat > /etc/httpd/conf.d/zz_${SVCPREFIX}.conf <<EOF
# this file must be loaded (alphabetically) after wsgi.conf

# need this for some of the RESTful URIs we can generate
AllowEncodedSlashes On

WSGIPythonOptimize 1
WSGIDaemonProcess ${SVCPREFIX} processes=4 threads=4 user=${SVCUSER} maximum-requests=2000
WSGIScriptAlias /${SVCPREFIX} ${TAGFILERDIR}/wsgi/tagfiler.wsgi

WSGISocketPrefix ${RUNDIR}/wsgi

Alias /${SVCPREFIX}/static /var/www/html/${SVCPREFIX}/static

<Location /${SVCPREFIX}>

    WSGIProcessGroup ${SVCPREFIX}
    
    # AuthType Digest
    # AuthName "${SVCPREFIX}"
    # AuthDigestDomain /${SVCPREFIX}/
    # AuthUserFile /etc/httpd/passwd/passwd
    # Require valid-user

    # site can disable redundant service logging by adding env=!dontlog to their CustomLog or similar directives
    SetEnv dontlog

</Location>

<Location /${SVCPREFIX}/static>

   # we don't want authentication on the applet download etc.
   Satisfy Any
   Allow from all

   <IfModule mod_expires.c>
      ExpiresActive On
      ExpiresDefault "access plus 1 hour"
   </IfModule>

   UnsetEnv dontlog

</Location>

EOF

signedjar=signed-isi-misd-tagfiler-upload-applet.jar
namespace=edu/isi/misd/tagfiler/util
props=tagfiler.properties


detect_service()
{
    [[ -x /sbin/chkconfig ]] && { /sbin/chkconfig --list "$1" 2> /dev/null | grep :on ; } && return 0
    [[ -x /bin/systemctl ]] && { /bin/systemctl is-enabled "$1".service 2> /dev/null | grep enabled ; } && return 0
    return 1
}

SYSLOGSVC=
[[ -f /etc/syslog.conf ]] && detect_service "syslog" && SYSLOGSVC=syslog
[[ -f /etc/rsyslog.conf ]] && detect_service "rsyslog" && SYSLOGSVC=rsyslog
[[ -z "$SYSLOGSVC" ]] && {
    echo "Failed to detect system logging service, cannot enable logging properly" >&2
    exit 1
}

if [[ -d /etc/logrotate.d/ ]]
then
    cat > /etc/logrotate.d/${SVCPREFIX} <<EOF
/var/log/${SVCPREFIX} {
    missingok
    nocompress
    dateext
    daily
    rotate 31
    maxage 31
    ifempty
    sharedscripts
    postrotate
	/sbin/service $SYSLOGSVC restart 2> /dev/null 2> /dev/null || true
    endscript
}
EOF
fi

if grep -q "local1\..*|/var/log/${SVCPREFIX}" /etc/${SYSLOGSVC}.conf
then
    # disable old, conflicting entry
    TMPF=$(mktemp ${SYSLOGSVC}.conf.XXXXXXXXXX)
    cat /etc/${SYSLOGSVC}.conf | sed -e 's:^\( *# *\)\(.*local1\..*|/var/log/${SVCPREFIX}\):# \2:' > $TMPF && cat $TMPF > /etc/${SYSLOGSVC}.conf
    rm $TMPF
    service ${SYSLOGSVC} restart
fi
[[ -p /var/log/${SVCPREFIX} ]] && rm -f /var/log/${SVCPREFIX}


# enable new logging entry
if ! grep -q "^ *local1\..*/var/log/${SVCPREFIX}" /etc/${SYSLOGSVC}.conf
then
    cat >> /etc/${SYSLOGSVC}.conf <<EOF

# ${SVCPREFIX} log entries
local1.*                                        /var/log/${SVCPREFIX}

EOF
    service ${SYSLOGSVC} restart
fi

