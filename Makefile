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

INSTALLDIR=$(shell python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()')/tagfiler

WSGIFILE=tagfiler.wsgi

IMAGEBASES= \
	ui-bg_diagonals-thick_18_b81900_40x40.png \
	ui-bg_diagonals-thick_20_666666_40x40.png \
	ui-bg_flat_10_000000_40x100.png \
	ui-bg_glass_100_f6f6f6_1x400.png \
	ui-bg_glass_100_fdf5ce_1x400.png \
	ui-bg_glass_65_ffffff_1x400.png \
	ui-bg_gloss-wave_35_f6a828_500x100.png \
	ui-bg_highlight-soft_100_eeeeee_1x100.png \
	ui-bg_highlight-soft_75_ffe45c_1x100.png \
	ui-icons_222222_256x240.png \
	ui-icons_228ef1_256x240.png \
	ui-icons_ef8c08_256x240.png \
	ui-icons_ffd27a_256x240.png \
	ui-icons_ffffff_256x240.png

SCRIPTFILEBASES=logo.png \
				functions.js \
				index.html \
				jquery.js \
				jquery-ui.js \
				jquery-ui-timepicker-addon.js \
				jquery.contextMenu.js \
				jquery.form.js \
				main.css \
				jquery-ui.css \
				StyleSheet.css \
				jquery.contextMenu.css \
				calendar.gif \
				new.png \
				delete.png \
				arrow_left.png \
				arrow_right.png \
				bullet_arrow_down.png \
				bullet_arrow_up.png \
				control_stop.png \
				minus.png \
				plus.png \
				ajax-loader.gif \
				back.jpg \
				forward.jpg \
				back_disabled.jpg \
				forward_disabled.jpg \
				arrow_down.gif

FILEBASES=dataserv_app.py rest_fileio.py subjects.py \
	url_ast.py url_lex.py url_parse.py \
	__init__.py

BINFILEBASES=tagfiler-webauthn2-deploy.py \
	tagfiler-webauthn2-manage.py

FILES=$(FILEBASES:%=src/tagfiler/%)
BINFILES=$(BINFILEBASES:%=scripts/%)
SCRIPTFILES=$(SCRIPTFILEBASES:%=static/%)
WSGI=$(WSGIFILE:%=wsgi/%)
IMAGEFILES=$(IMAGEBASES:%=images/%)

# turn off annoying built-ins
.SUFFIXES:

$(HOME)/.tagfiler.predeploy:
	yum -y --skip-broken install policycoreutils-python httpd mod_ssl mod_wsgi python{,-psycopg2,-webpy,-ply,-dateutil,-json,-simplejson,-oauth,-suds} || true
	touch $(HOME)/.tagfiler.predeploy

deploy: $(HOME)/.tagfiler.predeploy install
	./bin/deploy.sh $(INSTALLSVC)
	#./bin/register-software-version.sh $(INSTALLSVC)

install: $(FILES) $(WSGI)
	mkdir -p /usr/local/sbin
	mkdir -p /var/www/html/$(INSTALLSVC)/static/images
	mkdir -p $(INSTALLDIR)/wsgi
	mkdir -p /var/www/html/$(INSTALLSVC)/static/
	rsync -av $(FILES) $(INSTALLDIR)/.
	rsync -av $(WSGI) $(INSTALLDIR)/wsgi/.
	rsync -av $(SCRIPTFILES) /var/www/html/$(INSTALLSVC)/static/.
	rsync -av $(IMAGEFILES) /var/www/html/$(INSTALLSVC)/static/images/.
	rsync -av $(BINFILES) /usr/local/bin/.
	rsync -av $(SBINFILES) /usr/local/sbin/.
	#./bin/register-software-version.sh $(INSTALLSVC)

restart: force install
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
