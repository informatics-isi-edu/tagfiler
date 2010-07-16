#!/bin/sh

# set the services to run automatically?
chkconfig httpd on

# crowd authentication in ssl.conf
CONFFILE=/etc/httpd/conf.d/ssl.conf
if test -e $CONFFILE
then
	# save ssl.conf
	cp $CONFFILE $CONFFILE.`date +%F.%H:%M:%S`
	
	# insert crowd authentication in the <VirtualHost> section
	TMPFILE=`mktemp $CONFFILE.XXXXXX`
	cat $CONFFILE | sed 's/<\/VirtualHost>/\
	AllowEncodedSlashes On\
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
