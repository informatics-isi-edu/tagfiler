#!/bin/sh

# you can set this to override...
HOME_HOST=

# default to `hostname` setting
HOST=$(hostname)
HOME_HOST=${HOME_HOST:-$HOST}

# create local helper scripts
mkdir -p /etc/httpd/passwd

cat > ${HOME}/README-${SVCPREFIX} <<EOF
This service requires passwords to be configured via:

  htdigest /etc/httpd/passwd/passwd "${SVCUSER}" username

for each user you wish to add.

EOF

# register our service code
cat > /etc/httpd/conf.d/zz_${SVCPREFIX}.conf <<EOF
# this file must be loaded (alphabetically) after wsgi.conf

# need this for some of the RESTful URIs we can generate
AllowEncodedSlashes On

WSGIDaemonProcess ${SVCPREFIX} processes=4 threads=15 user=${SVCUSER}

WSGIScriptAlias /${SVCPREFIX} ${PSOCDIR}/dataserv.wsgi

WSGISocketPrefix ${RUNDIR}/wsgi

<Directory ${PSOCDIR}>

    WSGIProcessGroup ${SVCPREFIX}

    SetEnv ${SVCPREFIX}.source_path ${PSOCDIR}
    SetEnv ${SVCPREFIX}.dbnstr postgres
    SetEnv ${SVCPREFIX}.dbstr ${SVCUSER}
    SetEnv ${SVCPREFIX}.home https://${HOME_HOST}
    SetEnv ${SVCPREFIX}.store_path ${DATADIR}
    SetEnv ${SVCPREFIX}.template_path ${PSOCDIR}/templates
    SetEnv ${SVCPREFIX}.chunkbytes 1048576

</Directory>

EOF

