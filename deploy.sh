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

cp dbsetup-*-demo.sh /home/${SVCUSER}/
chown ${SVCUSER}: /home/${SVCUSER}/dbsetup-*-demo.sh
chmod a+x /home/${SVCUSER}/dbsetup-*-demo.sh

# setup db tables
runuser -c "~${SVCUSER}/dbsetup.sh ${HOME_HOST} ${SVCPREFIX} \"${admin}\" \"${uploader}\" \"${downloader}\" \"${curator}\" \"${grader}\" \"${DEMO}\"" - ${SVCUSER}

# register our service code
cat > /etc/httpd/conf.d/zz_${SVCPREFIX}.conf <<EOF
# this file must be loaded (alphabetically) after wsgi.conf

# need this for some of the RESTful URIs we can generate
AllowEncodedSlashes On

WSGIDaemonProcess ${SVCPREFIX} processes=32 threads=4 user=${SVCUSER}

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

cat > /usr/sbin/runuser-rsh <<EOF
#!/bin/sh

# support basic RSH args on top of runuser for local commands like rsync

in_options=true
TARGET_USER=

usage()
{
    cat <<E2OF
usage: \$0 [-l <user>] hostname cmd [arg]...

Runs "cmd arg..." locally, using runuser if a target user is specified.
Hostname is ignored for compatibility with RSH for localhost.

E2OF
}

error()
{
    cat <<E2OF
\$0: \$@
E2OF
    usage
    exit 1
}

while [[ -n "\${in_options}" ]]
do
  case "\$1" in
      -l)
	  TARGET_USER="\$2"
	  shift 2
	  ;;

      --)
	  shift
	  in_options=
	  ;;

      -*)
	  error Unsupported option flag "\\"\$1\\"".
	  ;;

      *)
	  in_options=
	  ;;
  esac
done

# discard hostname
shift

[[ \$# -gt 0 ]] || error Expected command and argument list

if [[ -n "\${TARGET_USER}" ]]
then
    # run via runuser with target user
    commandstring="\$1"
    shift

    for arg in "\$@"
    do
      commandstring+=" \\"\$(sed -e 's/\\"/\\\\\\"/g' <<< "\$arg")\\""
    done

    runuser -c "\${commandstring}" - "\${TARGET_USER}"
else
    # run command directly since there is no target user to switch to
    exec "\$@"
fi
EOF

if [[ -d /etc/logrotate.d/ ]]
then
    cat > /etc/logrotate.d/${SVCPREFIX} <<EOF
/var/log/${SVCPREFIX} {
    missingok
    dateext
    daily
    rotate 31
    maxage 31
    ifempty
    sharedscripts
    postrotate
	/bin/kill -HUP \`cat /var/run/syslogd.pid 2> /dev/null\` 2> /dev/null || true
	rsync --delete-after -a -e /usr/sbin/runuser-rsh /var/log/${SVCPREFIX}-* ${SVCUSER}@localhost:/var/www/${SVCPREFIX}-logs/ 2>/dev/null || true
    endscript
}
EOF
fi

# clean up old logging hacks
[[ -f /etc/sysconfig/${SVCPREFIX}-log ]] && rm -f /etc/sysconfig/${SVCPREFIX}-log
[[ -f /usr/sbin/${SVCPREFIX}-log ]] && rm -f /usr/sbin/${SVCPREFIX}-log 
[[ -f /etc/rc.d/init.d/${SVCPREFIX}-log ]] && {

    service ${SVCPREFIX}-log stop
    chkconfig ${SVCPREFIX}-log off
    rm /etc/rc.d/init.d/${SVCPREFIX}-log

}
if grep -q "local1\..*|/var/log/${SVCPREFIX}" /etc/syslog.conf
then
    # disable old, conflicting entry
    TMPF=$(mktemp syslog.conf.XXXXXXXXXX)
    cat /etc/syslog.conf | sed -e 's:^\( *local1\..*|/var/log/${SVCPREFIX}\):# \1:' > $TMPF && cat $TMPF > /etc/syslog.conf
    rm $TMPF
    service syslog restart
fi
[[ -p /var/log/${SVCPREFIX} ]] && rm -f /var/log/${SVCPREFIX}


# enable new logging entry
if ! grep -q "local1\..*|/var/log/${SVCPREFIX}" /etc/syslog.conf
then
    cat >> /etc/syslog.conf <<EOF

# ${SVCPREFIX} log entries
local1.*                                        /var/log/${SVCPREFIX}

EOF
    service syslog restart
fi

