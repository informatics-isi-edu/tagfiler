
INSTALLSVC=tagfiler
INSTALLDIR=/var/www/$(INSTALLSVC)

FILES=dataserv.wsgi \
	dataserv_app.py rest_fileio.py \
	url_ast.py url_lex.py url_parse.py

TEMPLATEBASES=Top.html Bottom.html Commands.html \
	FileForm.html NameForm.html UrlForm.html \
	FileList.html UriList.txt ConfirmForm.html \
	TagdefExisting.html TagdefNew.html \
	FileTagExisting.html FileTagNew.html \
	QueryAdd.html QueryView.html QueryViewStatic.html \
	Error.html

TEMPLATES=$(TEMPLATEBASES:%=templates/%)

# turn off annoying built-ins
.SUFFIXES:

$(HOME)/.tagfiler.predeploy:
	yum -y --skip-broken install httpd mod_wsgi postgresql{,-devel,-server} python{,-psycopg2,-webpy,-ply} || true
	service postgresql initdb || true
	touch $(HOME)/.tagfiler.predeploy

deploy: $(HOME)/.tagfiler.predeploy
	./deploy.sh $(INSTALLSVC)

install: $(FILES) $(TEMPLATES)
	rsync -av $(FILES) $(INSTALLDIR)/.
	rsync -av $(TEMPLATES) $(INSTALLDIR)/templates/.

restart: force install
	service httpd restart

clean: force
	rm -rf $(INSTALLDIR)
	rm -f $(HOME)/.tagfiler.predeploy

force:

