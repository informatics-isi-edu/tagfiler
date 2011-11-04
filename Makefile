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

RELEASE=$(shell svn info  | grep "Revision:" | awk  '{print $$2}')

INSTALLSVC=tagfiler
APPLETBUILD=../dei_applet-trunk

INSTALLDIR=$(shell python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()')/tagfiler

WEBROOTDIR=/var/www
WEBSTATICDIR=$(WEBROOTDIR)/html/$(INSTALLSVC)/static

WSGIFILE=tagfiler.wsgi

SCRIPTFILES=functions.js \
			jquery.js \
			main.css \
			calendar.gif \
			new.png \
			delete.png \
			arrow_left.png \
			arrow_right.png \
			bullet_arrow_down.png \
			bullet_arrow_up.png \
			control_stop.png

FILES=dataserv_app.py rest_fileio.py subjects.py \
	url_ast.py url_lex.py url_parse.py \
	__init__.py

WEBSTATICFILES=logo.png \
	functions.js \
	jquery.js \
	main.css \
	calendar.gif \
	new.png \
	delete.png \
	arrow_left.png \
	arrow_right.png \
	bullet_arrow_down.png \
	bullet_arrow_up.png \
	control_stop.png

TEMPLATEBASES=Top.html Bottom.html Commands.html \
	FileForm.html NameForm.html UrlForm.html \
	FileList.html FileUriList.txt ConfirmForm.html \
	Homepage.html \
	FileTagValBlock.html \
	TagdefExisting.html \
	FileTagExisting.html FileTagUriList.txt FileTagValExisting.html \
	TagdefNewShortcut.html \
	QueryAdd.html QueryView.html QueryViewStatic.html \
	TreeUpload.html TreeDownload.html TreeStatus.html \
	Error.html AppletError.html \
	LogList.html LogUriList.html Contact.html DatasetForm.html \
	RemoveTagValueForm.html SetTagForm.html SetTagValueForm.html TagValueForm.html

TEMPLATES=$(TEMPLATEBASES:%=templates/%)
WSGI=$(WSGIFILE:%=wsgi/%)

# turn off annoying built-ins
.SUFFIXES:

$(HOME)/.tagfiler.predeploy:
	yum -y --skip-broken install postgresql{,-devel,-server} || true
	yum -y --skip-broken install httpd mod_ssl mod_wsgi python{,-psycopg2,-webpy,-ply,-dateutil,-json} || true
	service postgresql initdb || true
	touch $(HOME)/.tagfiler.predeploy

deploy: $(HOME)/.tagfiler.predeploy install
	./deploy.sh $(INSTALLSVC) $(APPLETBUILD)
	./register-software-version.sh $(INSTALLSVC)

install: $(FILES) $(TEMPLATES) $(WSGI)
	mkdir -p $(INSTALLDIR)/templates
	mkdir -p $(INSTALLDIR)/wsgi
	mkdir -p /var/www/html/$(INSTALLSVC)/static/
	mkdir -p $(WEBSTATICDIR)
	rsync -av $(FILES) $(INSTALLDIR)/.
	rsync -av $(TEMPLATES) $(INSTALLDIR)/templates/.
	python $(shell { echo 'import distutils.sysconfig' ; echo 'print distutils.sysconfig.get_python_lib()'; } | python)/web/template.py --compile $(INSTALLDIR)/templates/
	rsync -av $(WSGI) $(INSTALLDIR)/wsgi/.
	rsync -av $(SCRIPTFILES) /var/www/html/$(INSTALLSVC)/static/.
	rsync -av $(WEBSTATICFILES) $(WEBSTATICDIR)/.
	./register-software-version.sh $(INSTALLSVC)

restart: force install
	service httpd restart

deployPSOC: $(HOME)/.tagfiler.predeploy installPSOC
	./deploy.sh $(INSTALLSVC) $(APPLETBUILD) psoc-pilot

installPSOC: install
	make --no-print-directory -f psoc/Makefile install

restartPSOC: force installPSOC
	service httpd restart

clean: force
	rm -rf $(INSTALLDIR)
	rm -f $(HOME)/.tagfiler.predeploy

force:

rpm_build:
	rm -fR build dist tagfiler.egg-info
	python setup.py bdist_rpm --binary-only --release $(RELEASE) --post-install post-script

rpm: rpm_build
	rpm -Uvh $(shell find . -name '*.rpm')
