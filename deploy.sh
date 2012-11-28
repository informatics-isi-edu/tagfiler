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

######
# NOTE: you can leave all this as defaults and modify Makefile
# which invokes this with SVCPREFIX...
######

# role mapping used in default data and ACLs

# default for trial-data demo
admin="${admin:-admin}"
uploader="${uploader:-uploader}"
downloader="${downloader:-downloader}"
curator="${curator:-coordinator}"
grader="${grader:-grader}"

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
DEMO=${3}

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

# set the services to run automatically?
chkconfig httpd on
chkconfig postgresql on

SVCHOME=$(eval "echo ~${SVCUSER}")

# finish initializing system for our service
semanage fcontext --add --ftype "" --type httpd_sys_rw_content_t "${DATADIR}(/.*)?" \
    || semanage fcontext --add --ftype "" --type httpd_sys_script_rw_t "${DATADIR}(/.*)?"
mkdir -p ${DATADIR}
restorecon -rvF ${DATADIR}

mkdir -p ${RUNDIR}

mkdir -p ${LOGDIR}
restorecon -rvF ${LOGDIR}

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
chown ${SVCUSER}: ${LOGDIR}
chmod og= ${LOGDIR}

if runuser -c "psql -c 'select * from pg_user' ${PGADMIN}" - ${PGADMIN} | grep ${SVCUSER} 1>/dev/null
then
    :
else
	runuser -c "createuser -S -D -R ${SVCUSER}" - ${PGADMIN}
fi

runuser -c "dropdb ${SVCUSER}" - ${PGADMIN}
runuser -c "createdb -O ${SVCUSER} ${SVCUSER}" - ${PGADMIN}


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

cp dbsetup.sh ${SVCHOME}/dbsetup.sh
chown ${SVCUSER}: ${SVCHOME}/dbsetup.sh
chmod a+x ${SVCHOME}/dbsetup.sh

cp dbsetup-*-demo.sh ${SVCHOME}/
chown ${SVCUSER}: ${SVCHOME}/dbsetup-*-demo.sh
chmod a+x ${SVCHOME}/dbsetup-*-demo.sh

# setup db tables
runuser -c "${SVCHOME}/dbsetup.sh ${HOME_HOST} ${SVCPREFIX} \"${admin}\" \"${uploader}\" \"${downloader}\" \"${curator}\" \"${grader}\" \"${DEMO}\"" - ${SVCUSER}

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
	/usr/bin/rsync --delete-after -a -e /usr/local/sbin/runuser-rsh /var/log/${SVCPREFIX}-* ${SVCUSER}@localhost:/var/www/${SVCPREFIX}-logs/ 2>/dev/null || true
    endscript
}
EOF
fi

# clean up old logging hacks
[[ -f /etc/sysconfig/${SVCPREFIX}-log ]] && rm -f /etc/sysconfig/${SVCPREFIX}-log
[[ -f /usr/sbin/runuser-rsh ]] && rm -f /usr/sbin/runuser-rsh
[[ -f /usr/sbin/${SVCPREFIX}-log ]] && rm -f /usr/sbin/${SVCPREFIX}-log 
[[ -f /etc/rc.d/init.d/${SVCPREFIX}-log ]] && {

    service ${SVCPREFIX}-log stop
    chkconfig ${SVCPREFIX}-log off
    rm /etc/rc.d/init.d/${SVCPREFIX}-log

}

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

