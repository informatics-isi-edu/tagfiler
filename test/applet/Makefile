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

# to overwrite these variables, run the make command with the arguments USER=... HOST=... PASSWORD=... INPUT_DIR=...
USER=$(shell whoami)
HOST=localhost
PASSWORD=just4demo
INPUT_DIR=/home/$(USER)/tagfiler/test/applet/input
INSTANCES=20

# CLASSPATH for running the test
JAR_DIR=/home/$(USER)/.icedteaplugin/cache/https/$(HOST)/tagfiler/static
JAR_LIB=lib/TagfilerClient.jar:$(JAR_DIR)/apache-mime4j-0.6.jar:$(JAR_DIR)/commons-codec-1.4.jar:$(JAR_DIR)/commons-logging-1.1.1.jar:$(JAR_DIR)/httpclient-4.0.3.jar:$(JAR_DIR)/httpcore-4.0.1.jar:$(JAR_DIR)/httpmime-4.0.3.jar:$(JAR_DIR)/isi-misd-tagfiler-upload.jar:$(JAR_DIR)/jakarta-commons-httpclient-3.1.jar:$(JAR_DIR)/jsse.jar:$(JAR_DIR)/plugin.jar:$(JAR_DIR)/json-org.jar

# turn off annoying built-ins
.SUFFIXES:

build:
	ant -Duser.name=$(USER) -Dhost.name=$(HOST)
	
# launch multiple instances simultaneously to run full upload or download sequences. 
test: build
	JAR_LIB=$(JAR_LIB) PASSWORD=$(PASSWORD) HOST=$(HOST) USER=$(USER) INPUT=$(INPUT_DIR) sh client.sh $(INSTANCES)
