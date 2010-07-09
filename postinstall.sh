#!/bin/sh

export SVCPREFIX=${1}
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
	${SVCDIR}/deploydb.sh
	touch $(HOME)/.${SVCPREFIX}.deploydb
fi

if ! test -e ${HOME}/.${SVCPREFIX}.deployhttpd
then
	${SVCDIR}/deployhttpd.sh
	touch $(HOME)/.${SVCPREFIX}.deployhttpd
fi

service httpd restart
