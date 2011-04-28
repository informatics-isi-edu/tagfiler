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

cp dbsetup.sh /home/${SVCUSER}/dbsetup.sh
chown ${SVCUSER}: /home/${SVCUSER}/dbsetup.sh
chmod a+x /home/${SVCUSER}/dbsetup.sh

cp dbsetup-psoc-demo.sh /home/${SVCUSER}/dbsetup-psoc-demo.sh
chown ${SVCUSER}: /home/${SVCUSER}/dbsetup-psoc-demo.sh
chmod a+x /home/${SVCUSER}/dbsetup-psoc-demo.sh

# setup db tables
runuser -c "~${SVCUSER}/dbsetup.sh ${HOME_HOST} ${SVCPREFIX} \"${admin}\" \"${uploader}\" \"${downloader}\" \"${curator}\" \"${grader}\"" - ${SVCUSER}

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

