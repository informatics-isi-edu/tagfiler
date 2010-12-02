RELEASE=$(shell svn info  | grep "Revision:" | awk  '{print $$2}')

INSTALLSVC=tagfiler
APPLETBUILD=../dei_applet-trunk

INSTALLDIR=$(shell python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()')/tagfiler

WEBROOTDIR=/var/www
WEBSTATICDIR=$(WEBROOTDIR)/html/$(INSTALLSVC)/static

WSGIFILE=tagfiler.wsgi

SCRIPTFILES=functions.js main.css

FILES=dataserv_app.py rest_fileio.py \
	url_ast.py url_lex.py url_parse.py \
	__init__.py

WEBSTATICFILES=logo.png \
	functions.js \
	main.css

TEMPLATEBASES=Top.html Bottom.html Commands.html \
	FileForm.html NameForm.html UrlForm.html \
	FileList.html FileUriList.txt ConfirmForm.html \
	FileTagValBlock.html \
	TagdefExisting.html \
	FileTagExisting.html FileTagUriList.txt FileTagValExisting.html \
	TagdefNewShortcut.html \
	QueryAdd.html QueryView.html QueryViewStatic.html \
	TreeUpload.html TreeDownload.html TreeStatus.html \
	Error.html AppletError.html \
	LogList.html LogUriList.html Contact.html

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

install: $(FILES) $(TEMPLATES) $(WSGI)
	mkdir -p $(INSTALLDIR)/templates
	mkdir -p $(INSTALLDIR)/wsgi
	mkdir -p /var/www/html/$(INSTALLSVC)/static/
	mkdir -p $(WEBSTATICDIR)
	rsync -av $(FILES) $(INSTALLDIR)/.
	rsync -av $(TEMPLATES) $(INSTALLDIR)/templates/.
	rsync -av $(WSGI) $(INSTALLDIR)/wsgi/.
	rsync -av $(SCRIPTFILES) /var/www/html/$(INSTALLSVC)/static/.
	rsync -av $(WEBSTATICFILES) $(WEBSTATICDIR)/.

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
