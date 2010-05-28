
# change INSTALLHOST to an FQDN to install to a remote testing VM etc.
INSTALLHOST=localhost
INSTALLSVC=tagfiler
INSTALLDIRBASE=/var/www/$(INSTALLSVC)
INSTALLDIR=root@$(INSTALLHOST):$(INSTALLDIRBASE)

FILES=dataserv.wsgi \
	dataserv_app.py rest_fileio.py \
	url_ast.py url_lex.py url_parse.py

TEMPLATEBASES=Top.html Bottom.html Commands.html \
	FileForm.html NameForm.html UrlForm.html \
	FileList.html \
	TagdefExisting.html TagdefNew.html \
	FileTagExisting.html FileTagNew.html \
	QueryAdd.html QueryView.html

TEMPLATES=$(TEMPLATEBASES:%=templates/%)

# turn off annoying built-ins
.SUFFIXES:

deploy:
	rsync -av deploy.sh root@$(INSTALLHOST):.
	ssh root@$(INSTALLHOST) ./deploy.sh $(INSTALLSVC)

install: $(FILES) $(TEMPLATES)
	rsync -av $(FILES) $(INSTALLDIR)/.
	rsync -av $(TEMPLATES) $(INSTALLDIR)/templates/.

restart: force install
	ssh -l root $(INSTALLHOST) service httpd restart

force:

