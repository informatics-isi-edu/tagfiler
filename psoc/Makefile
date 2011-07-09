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

INSTALLSVC=tagfiler

INSTALLDIR=$(shell python -c 'import distutils.sysconfig;print distutils.sysconfig.get_python_lib()')/tagfiler

WEBROOTDIR=/var/www
WEBSTATICDIR=$(WEBROOTDIR)/html/$(INSTALLSVC)/static

SCRIPTBASES=psoc.js \
	jquery-ui.js \
	jquery-ui.css

SCRIPTFILES=$(SCRIPTBASES:%=psoc/%)

IMAGEBASES=minus.png \
	plus.png \
	template.png \
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

IMAGEFILES=$(IMAGEBASES:%=psoc/images/%)

TEMPLATEBASES=psoc.html

TEMPLATES=$(TEMPLATEBASES:%=psoc/templates/%)

SVCDIR=/var/www/$(INSTALLSVC)
DATADIR=$(SVCDIR)-data
PSOCNAME="name=DEMO%3A%20Create%20PSOC%20entries"
PSOCDIR=$(DATADIR)/$(PSOCNAME)
PSOCFILE=$(PSOCDIR)/admin-psoctemplate


# turn off annoying built-ins
.SUFFIXES:

install: $(TEMPLATES)
	mkdir -p /var/www/html/$(INSTALLSVC)/static/images
	rsync -av $(TEMPLATES) $(INSTALLDIR)/templates/.
	rsync -av $(SCRIPTFILES) /var/www/html/$(INSTALLSVC)/static/.
	rsync -av $(IMAGEFILES) /var/www/html/$(INSTALLSVC)/static/images/.
	rm -fR $(PSOCDIR)
	mkdir -p $(PSOCDIR)
	cp $(INSTALLDIR)/templates/psoc.html $(PSOCFILE)
	chmod go-r $(PSOCFILE)
	chown -R $(INSTALLSVC):apache $(PSOCDIR)
