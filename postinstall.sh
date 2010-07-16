#!/bin/sh

export SVCPREFIX=${1}
export PSOCDIR=$(python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()')/psoc
export SVCUSER=${SVCPREFIX}
export DATADIR=${SVCDIR}/${SVCPREFIX}-data
export RUNDIR=/var/run/wsgi

if ! test -e ${HOME}/.${SVCPREFIX}.predeploy
then
	# finish initializing system for our service
	mkdir -p ${DATADIR}
	mkdir -p ${RUNDIR}
	chown ${SVCUSER}: ${DATADIR}
	chmod og=rx ${DATADIR}
	service postgresql initdb || true
	touch $(HOME)/.${SVCPREFIX}.predeploy
fi
	
if ! test -e ${HOME}/.${SVCPREFIX}.deploydb
then
	${PSOCDIR}/deploydb.sh
	touch $(HOME)/.${SVCPREFIX}.deploydb
fi

if ! test -e /root/.deployhttpd
then
	${PSOCDIR}/deployhttpd.sh
	touch /root/.deployhttpd
fi

if ! test -e ${HOME}/.${SVCPREFIX}.deploywsgi
then
	${PSOCDIR}/deploywsgi.sh
	touch $(HOME)/.${SVCPREFIX}.deploywsgi
fi

service httpd restart
