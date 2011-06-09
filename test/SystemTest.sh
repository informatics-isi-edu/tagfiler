#!/bin/sh

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

# Set in the following definitions your test values for:
#	<hostname>			- hostname of the service
#	<user>				- authentication user
#	<password>			- authentication password for user
#	<file>				- the path of the file to be uploaded

hostname=|the service hostname|
user=|the user|
password=|password for user|
file=|the path of the file to be uploaded|

usercookiefile="$user"cookiefile

HOST=https://$hostname
LOGIN=https://$hostname/webauthn/login
AUTHENTICATION="-d username=$user -d password=$password"
USER_COOKIE="-b $usercookiefile -c $usercookiefile"
COMMON_OPTIONS="-s -S -k"

LOGFILE=psoc.log
TEMPFILE=psocTemp
DATASET1=Spectrophotometry
DATASET2=Retinoblastoma
FILE=$file
URL=http://www.yahoo.com
TAG1=Location
TAG2=Color
DATASET1_TAG1_VALUE1=Los%20Angeles
DATASET1_TAG1_VALUE2=San%20Francisco
DATASET1_TAG2_VALUE=Green
DATASET2_TAG1_VALUE1=Los%20Angeles
DATASET2_TAG1_VALUE2=San%20Diego
DATASET2_TAG2_VALUE=Green

START=$(date +%s)

date > $LOGFILE
echo "" >> $LOGFILE

# Login

echo "curl $USER_COOKIE $COMMON_OPTIONS $AUTHENTICATION $LOGIN" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS $AUTHENTICATION $LOGIN >> $LOGFILE
echo "" >> $LOGFILE
echo "" >> $LOGFILE

# Tags Actions

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with POST" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"tag-1=$TAG1&type-1=text&multivalue-1=true&readpolicy-1=subjectowner&writepolicy-1=subjectowner&action=add\" \"$HOST/tagfiler/tagdef\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "tag-1=$TAG1&type-1=text&multivalue-1=true&readpolicy-1=subjectowner&writepolicy-1=subjectowner&action=add" "$HOST/tagfiler/tagdef" >> $LOGFILE
echo "" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef/$TAG1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with POST" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=ConfirmDelete\" \"$HOST/tagfiler/tagdef/$TAG1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=ConfirmDelete" "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo "" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with PUT" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X PUT \"$HOST/tagfiler/tagdef/$TAG1?typestr=text&multivalue=true&readpolicy-1=subjectowner&writepolicy-1=subjectowner\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X PUT "$HOST/tagfiler/tagdef/$TAG1?typestr=text&multivalue=true&readpolicy-1=subjectowner&writepolicy-1=subjectowner" >> $LOGFILE
echo "" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef/$TAG1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with DELETE" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE  \"$HOST/tagfiler/tagdef/$TAG1\"" >> $LOGFILE
echo "" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE  "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with POST" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"tag-1=$TAG1&type-1=text&multivalue-1=true&readpolicy-1=subjectowner&writepolicy-1=subjectowner&action=add\" \"$HOST/tagfiler/tagdef\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "tag-1=$TAG1&type-1=text&multivalue-1=true&readpolicy-1=subjectowner&writepolicy-1=subjectowner&action=add" "$HOST/tagfiler/tagdef" >> $LOGFILE
echo "" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef/$TAG1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG2\" tag with POST" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"tag-1=$TAG2&type-1=text&multivalue-1=false&readpolicy-1=subjectowner&writepolicy-1=subjectowner&action=add\" \"$HOST/tagfiler/tagdef\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "tag-1=$TAG2&type-1=text&multivalue-1=false&readpolicy-1=subjectowner&writepolicy-1=subjectowner&action=add" "$HOST/tagfiler/tagdef" >> $LOGFILE
echo "" >> $LOGFILE

echo "List \"$TAG2\" tag" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef/$TAG2\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef/$TAG2" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

# Dataset Actions

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\" \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET1\" dataset with POST"  >> $LOGFILE
date >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -F \"file=@$FILE\" \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -F "file=@$FILE" "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with url POST"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=put&url=$URL\" \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=put&url=$URL" "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query?versions=any\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query?versions=any" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with file POST"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -F \"file=@$FILE\" \"$HOST/tagfiler/file/name=$DATASET1;version=1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -F "file=@$FILE" "$HOST/tagfiler/file/name=$DATASET1;version=1" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query?versions=any\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query?versions=any" >> $LOGFILE
echo "" >> $LOGFILE

echo "Get/Download \"$DATASET1\" dataset"  >> $LOGFILE
date >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -o \"$TEMPFILE\" -X GET \"$HOST/tagfiler/file/name=$DATASET1;version=1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -o "$TEMPFILE" -X GET "$HOST/tagfiler/file/name=$DATASET1;version=1"
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Comparing download and upload files"  >> $LOGFILE
echo "diff \"$FILE\" \"$TEMPFILE\" >/dev/null 2>&1" >> $LOGFILE
diff "$FILE" "$TEMPFILE" >/dev/null 2>&1

if [ $? != 0 ]
then
    echo "Files are different" >> $LOGFILE
else
    echo "Files are identical" >> $LOGFILE
fi

echo "rm -f \"$TEMPFILE\""  >> $LOGFILE
rm -f "$TEMPFILE"
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" version=2 dataset with POST"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=ConfirmDelete\" \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=ConfirmDelete" "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" version=1 dataset with POST"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=ConfirmDelete\" \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=ConfirmDelete" "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -T \"$FILE\" \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -T "$FILE" "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -T \"$FILE\" \"$HOST/tagfiler/file/name=$DATASET1;version=1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -T "$FILE" "$HOST/tagfiler/file/name=$DATASET1;version=1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Get/Download \"$DATASET1\" dataset"  >> $LOGFILE
date >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -o \"$TEMPFILE\" -X GET \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -o "$TEMPFILE" -X GET "$HOST/tagfiler/file/name=$DATASET1"
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Comparing download and upload files"  >> $LOGFILE
echo "diff \"$FILE\" \"$TEMPFILE\" >/dev/null 2>&1" >> $LOGFILE
diff "$FILE" "$TEMPFILE" >/dev/null 2>&1

if [ $? != 0 ]
then
    echo "Files are different" >> $LOGFILE
else
    echo "Files are identical" >> $LOGFILE
fi

echo "rm -f \"$TEMPFILE\"" >> $LOGFILE
rm -f "$TEMPFILE"
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" dataset with DELETE"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE


# Adding Dataset Tags

echo "Define \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -T \"$FILE\" \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -T "$FILE" "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET2\" dataset with url POST"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=put&url=$URL\" \"$HOST/tagfiler/file/name=$DATASET2\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=put&url=$URL" "$HOST/tagfiler/file/name=$DATASET2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG1\" tag to dataset \"$DATASET1\" with values \"$DATASET1_TAG1_VALUE1\" and \"$DATASET1_TAG1_VALUE2\" using POST"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE1\" \"$HOST/tagfiler/tags/name=$DATASET1\"" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE2\" \"$HOST/tagfiler/tags/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE1" "$HOST/tagfiler/tags/name=$DATASET1" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE2" "$HOST/tagfiler/tags/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch \"$TAG1\" tag of dataset \"$DATASET1\""  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET1($TAG1)\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET1($TAG1)"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET1\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET1"  >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG2\" tag to dataset \"$DATASET1\" with value \"$DATASET1_TAG2_VALUE\" using PUT"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X PUT \"$HOST/tagfiler/tags/name=$DATASET1($TAG2=$DATASET1_TAG2_VALUE)\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X PUT "$HOST/tagfiler/tags/name=$DATASET1($TAG2=$DATASET1_TAG2_VALUE)" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch \"$TAG2\" tag of dataset \"$DATASET1\""  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET1($TAG2)\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET1($TAG2)"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET1\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET1"  >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG1\" tag to dataset \"$DATASET2\" with values \"$DATASET2_TAG1_VALUE1\" and \"$DATASET2_TAG1_VALUE2\" using POST"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE1\" \"$HOST/tagfiler/tags/name=$DATASET2\"" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE2\" \"$HOST/tagfiler/tags/name=$DATASET2\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE1" "$HOST/tagfiler/tags/name=$DATASET2" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE2" "$HOST/tagfiler/tags/name=$DATASET2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch \"$TAG1\" tag of dataset \"$DATASET2\""  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET2($TAG1)\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET2($TAG1)"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET2\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET2"  >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG2\" tag to dataset \"$DATASET2\" with value \"$DATASET2_TAG2_VALUE\" using PUT"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X PUT \"$HOST/tagfiler/tags/name=$DATASET2($TAG2=$DATASET2_TAG2_VALUE)\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X PUT "$HOST/tagfiler/tags/name=$DATASET2($TAG2=$DATASET2_TAG2_VALUE)" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch \"$TAG2\" tag of dataset \"$DATASET2\""  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET2($TAG2)\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET2($TAG2)"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET2\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET2"  >> $LOGFILE
echo "" >> $LOGFILE

# Queries

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\"" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -k -H \"Accept: text/uri-list\" -X GET \"$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\" OR \"$TAG1\" == \"$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -k -H \"Accept: text/uri-list\" -X GET \"$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1,$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1,$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\" AND \"$TAG1\" == \"$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -k -H \"Accept: text/uri-list\" -X GET \"$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1;$TAG1=$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1;$TAG1=$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET2_TAG1_VALUE2\" AND \"$TAG2\" == \"$DATASET1_TAG2_VALUE\"" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -k -H \"Accept: text/uri-list\" -X GET \"$HOST/tagfiler/query/$TAG1=$DATASET2_TAG1_VALUE2;$TAG2=$DATASET1_TAG2_VALUE\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET2_TAG1_VALUE2;$TAG2=$DATASET1_TAG2_VALUE" >> $LOGFILE
echo "" >> $LOGFILE

# Deleting tags from datasets

echo "Delete value \"$DATASET1_TAG1_VALUE1\" of \"$TAG1\" tag from dataset \"$DATASET1\" with POST" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -d \"tag=$TAG1&action=delete&value=$DATASET1_TAG1_VALUE1\" \"$HOST/tagfiler/tags/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -d "tag=$TAG1&action=delete&value=$DATASET1_TAG1_VALUE1" "$HOST/tagfiler/tags/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET1\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET1"  >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete value \"$DATASET1_TAG1_VALUE2\" of \"$TAG1\" tag from dataset \"$DATASET1\" with DELETE" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE \"$HOST/tagfiler/tags/name=$DATASET1($TAG1=$DATASET1_TAG1_VALUE2)\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE "$HOST/tagfiler/tags/name=$DATASET1($TAG1=$DATASET1_TAG1_VALUE2)" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET1\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET1"  >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag from dataset \"$DATASET1\" with DELETE" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE \"$HOST/tagfiler/tags/name=$DATASET1($TAG2)\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE "$HOST/tagfiler/tags/name=$DATASET1($TAG2)" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET1\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET1"  >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag from dataset \"$DATASET2\" with DELETE" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE \"$HOST/tagfiler/tags/name=$DATASET2($TAG1)\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE "$HOST/tagfiler/tags/name=$DATASET2($TAG1)" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET2\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET2"  >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag from dataset \"$DATASET2\" with DELETE" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE \"$HOST/tagfiler/tags/name=$DATASET2($TAG2)\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE "$HOST/tagfiler/tags/name=$DATASET2($TAG2)" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/tags/name=$DATASET2\""  >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -H "Accept: text/uri-list"  "$HOST/tagfiler/tags/name=$DATASET2"  >> $LOGFILE
echo "" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with DELETE" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE  \"$HOST/tagfiler/tagdef/$TAG1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE  "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo "" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag with DELETE" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE  \"$HOST/tagfiler/tagdef/$TAG2\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE  "$HOST/tagfiler/tagdef/$TAG2" >> $LOGFILE
echo "" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS \"$HOST/tagfiler/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep  "( " >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" dataset with DELETE"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE \"$HOST/tagfiler/file/name=$DATASET1\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE "$HOST/tagfiler/file/name=$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$DATASET2\" dataset with DELETE"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS -X DELETE \"$HOST/tagfiler/file/name=$DATASET2\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS -X DELETE "$HOST/tagfiler/file/name=$DATASET2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
echo "curl $USER_COOKIE $COMMON_OPTIONS  -H \"Accept: text/uri-list\"  \"$HOST/tagfiler/query\"" >> $LOGFILE
curl $USER_COOKIE $COMMON_OPTIONS  -H "Accept: text/uri-list"  "$HOST/tagfiler/query" >> $LOGFILE
echo "" >> $LOGFILE

date >> $LOGFILE
echo "" >> $LOGFILE

END=$(date +%s)
DIFF=$(( $END - $START ))
MIN=$(( $DIFF / 60 ))
SEC=$(( $DIFF % 60 ))

echo It took $MIN:$SEC minutes >> $LOGFILE
echo "" >> $LOGFILE
