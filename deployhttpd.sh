#!/bin/sh

# you can set this to override...
HOME_HOST=

# default to `hostname` setting
HOST=$(hostname)
HOME_HOST=${HOME_HOST:-$HOST}

# set the services to run automatically?
chkconfig httpd on

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

WSGIScriptAlias /${SVCPREFIX} ${SVCDIR}/dataserv.wsgi

WSGISocketPrefix ${RUNDIR}/wsgi

<Directory ${SVCDIR}>

    WSGIProcessGroup ${SVCPREFIX}

    SetEnv ${SVCPREFIX}.source_path ${SVCDIR}
    SetEnv ${SVCPREFIX}.dbnstr postgres
    SetEnv ${SVCPREFIX}.dbstr ${SVCUSER}
    SetEnv ${SVCPREFIX}.home https://${HOME_HOST}
    SetEnv ${SVCPREFIX}.store_path ${DATADIR}
    SetEnv ${SVCPREFIX}.template_path ${SVCDIR}/templates
    SetEnv ${SVCPREFIX}.chunkbytes 1048576

</Directory>

EOF

# crowd authentication in ssl.conf
CONFFILE=/etc/httpd/conf.d/ssl.conf
if test -e $CONFFILE
then
	# save ssl.conf
	cp $CONFFILE $CONFFILE.`date +%F.%H:%M:%S`
	
	# insert crowd authentication in the <VirtualHost> section
	TMPFILE=`mktemp $CONFFILE.XXXXXX`
	cat $CONFFILE | sed 's/<\/VirtualHost>/\
    AuthName psoc-demo\
    AuthType Basic\
    PerlAuthenHandler Apache::CrowdAuth\
    PerlSetVar CrowdAppName psoc-demo\
    PerlSetVar CrowdAppPassword $p$0c-D3mo!\
    PerlSetVar CrowdSOAPURL https:\/\/chi:8445\/crowd\/services\/SecurityServer\
    require valid-user\
    <LimitExcept GET PROPFIND OPTIONS REPORT>\
            Require valid-user\
    <\/LimitExcept>\
<\/VirtualHost>/' > $TMPFILE

	mv -f $TMPFILE $CONFFILE
fi

# disable python.conf file
CONFFILE=/etc/httpd/conf.d/python.conf
if test -e $CONFFILE
then
	mv $CONFFILE $CONFFILE.save
fi
	
# uncomment the LoadModule wsgi_module from wsgi.conf
CONFFILE=/etc/httpd/conf.d/wsgi.conf
if test -e $CONFFILE
then
	# save wsgi.conf
	cp $CONFFILE $CONFFILE.`date +%F.%H:%M:%S`
	
	TMPFILE=`mktemp $CONFFILE.XXXXXX`
	cat $CONFFILE | sed 's/^# LoadModule\(.*$\)/LoadModule\1/' > $TMPFILE
	
	mv -f $TMPFILE $CONFFILE
fi
