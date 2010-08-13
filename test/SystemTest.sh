#!/bin/sh

# Set in the following definitions your test values for:
#	<hostname>	- hostname of the service
#	<user>		- authentication user
#	<password>	- authentication password
#	<AuthType>	- authentication type (digest or basic)
#	<file>		- the path of the file to be uploaded
#	<tagfiler>	- the service prefix

HOST=http://<hostname>
AUTHENTICATION=<user>:<password>
AUTHENTICATION_METHOD=<AuthType>
FILE=<file>
SVCPREFIX=<tagfiler>

COMMON_OPTIONS="-s -S -k"
LOGFILE=psoc.log
TEMPFILE=psocTemp
DATASET1=Spectrophotometry
DATASET2=Retinoblastoma
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

# Tags Actions

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "tag-1=$TAG1&type-1=text&multivalue-1=true&readpolicy-1=anonymous&writepolicy-1=users&action=add" "$HOST/$SVCPREFIX/tagdef" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=ConfirmDelete" "$HOST/$SVCPREFIX/tagdef/$TAG1" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with PUT" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X PUT "$HOST/$SVCPREFIX/tagdef/$TAG1?typestr=text&multivalue=true" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with DELETE" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE  "$HOST/$SVCPREFIX/tagdef/$TAG1" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "tag-1=$TAG1&type-1=text&multivalue-1=true&readpolicy-1=anonymous&writepolicy-1=users&action=add" "$HOST/$SVCPREFIX/tagdef" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG2\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "tag-1=$TAG2&type-1=text&multivalue-1=false&readpolicy-1=anonymous&writepolicy-1=users&action=add" "$HOST/$SVCPREFIX/tagdef" >> $LOGFILE

echo "List \"$TAG2\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef/$TAG2" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

# Dataset Actions

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET1\" dataset with POST"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -F "file=@$FILE" "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with url POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=put&url=$URL" "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with file POST"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -F "file=@$FILE" "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Get/Download \"$DATASET1\" dataset"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -o "$TEMPFILE" -X GET "$HOST/$SVCPREFIX/file/$DATASET1"
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Comparing download and upload files"  >> $LOGFILE
diff "$FILE" "$TEMPFILE" >/dev/null 2>&1

if [ $? != 0 ]
then
    echo "Files are different" >> $LOGFILE
else
    echo "Files are identical" >> $LOGFILE
fi

rm -f "$TEMPFILE"
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" dataset with POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=ConfirmDelete" "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -T "$FILE" "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -T "$FILE" "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Get/Download \"$DATASET1\" dataset"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -o "$TEMPFILE" -X GET "$HOST/$SVCPREFIX/file/$DATASET1"
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Comparing download and upload files"  >> $LOGFILE
diff "$FILE" "$TEMPFILE" >/dev/null 2>&1

if [ $? != 0 ]
then
    echo "Files are different" >> $LOGFILE
else
    echo "Files are identical" >> $LOGFILE
fi

rm -f "$TEMPFILE"
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" dataset with DELETE"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE


# Adding Dataset Tags

echo "Define \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -T "$FILE" "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET2\" dataset with url POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=put&url=$URL" "$HOST/$SVCPREFIX/file/$DATASET2" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG1\" tag to dataset \"$DATASET1\" with values \"$DATASET1_TAG1_VALUE1\" and \"$DATASET1_TAG1_VALUE2\" using POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE1" "$HOST/$SVCPREFIX/tags/$DATASET1" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE2" "$HOST/$SVCPREFIX/tags/$DATASET1" >> $LOGFILE

echo "Fetch \"$TAG1\" tag of dataset \"$DATASET1\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET1/$TAG1"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG2\" tag to dataset \"$DATASET1\" with value \"$DATASET1_TAG2_VALUE\" using PUT"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X PUT "$HOST/$SVCPREFIX/tags/$DATASET1/$TAG2=$DATASET1_TAG2_VALUE" >> $LOGFILE

echo "Fetch \"$TAG2\" tag of dataset \"$DATASET1\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET1/$TAG2"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG1\" tag to dataset \"$DATASET2\" with values \"$DATASET2_TAG1_VALUE1\" and \"$DATASET2_TAG1_VALUE2\" using POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE1" "$HOST/$SVCPREFIX/tags/$DATASET2" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE2" "$HOST/$SVCPREFIX/tags/$DATASET2" >> $LOGFILE

echo "Fetch \"$TAG1\" tag of dataset \"$DATASET2\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET2/$TAG1"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG2\" tag to dataset \"$DATASET2\" with value \"$DATASET2_TAG2_VALUE\" using PUT"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X PUT "$HOST/$SVCPREFIX/tags/$DATASET2/$TAG2=$DATASET2_TAG2_VALUE" >> $LOGFILE

echo "Fetch \"$TAG2\" tag of dataset \"$DATASET2\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET2/$TAG2"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

# Queries

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -H "Accept: text/uri-list" -X GET "$HOST/$SVCPREFIX/query/$TAG1=$DATASET1_TAG1_VALUE1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\" OR \"$TAG1\" == \"$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -H "Accept: text/uri-list" -X GET "$HOST/$SVCPREFIX/query/$TAG1=$DATASET1_TAG1_VALUE1,$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\" AND \"$TAG1\" == \"$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -H "Accept: text/uri-list" -X GET "$HOST/$SVCPREFIX/query/$TAG1=$DATASET1_TAG1_VALUE1;$TAG1=$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET2_TAG1_VALUE2\" AND \"$TAG2\" == \"$DATASET1_TAG2_VALUE\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -H "Accept: text/uri-list" -X GET "$HOST/$SVCPREFIX/query/$TAG1=$DATASET2_TAG1_VALUE2;$TAG2=$DATASET1_TAG2_VALUE" >> $LOGFILE
echo "" >> $LOGFILE

# Deleting tags from datasets

echo "Delete value \"$DATASET1_TAG1_VALUE1\" of \"$TAG1\" tag from dataset \"$DATASET1\" with POST" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -d "tag=$TAG1&action=delete&value=$DATASET1_TAG1_VALUE1" "$HOST/$SVCPREFIX/tags/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete value \"$DATASET1_TAG1_VALUE2\" of \"$TAG1\" tag from dataset \"$DATASET1\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE "$HOST/$SVCPREFIX/tags/$DATASET1/$TAG1=$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag from dataset \"$DATASET1\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE "$HOST/$SVCPREFIX/tags/$DATASET1/$TAG2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag from dataset \"$DATASET2\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE "$HOST/$SVCPREFIX/tags/$DATASET2/$TAG1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag from dataset \"$DATASET2\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE "$HOST/$SVCPREFIX/tags/$DATASET2/$TAG2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with DELETE" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE  "$HOST/$SVCPREFIX/tagdef/$TAG1" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag with DELETE" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE  "$HOST/$SVCPREFIX/tagdef/$TAG2" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" dataset with DELETE"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE "$HOST/$SVCPREFIX/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$DATASET2\" dataset with DELETE"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS -X DELETE "$HOST/$SVCPREFIX/file/$DATASET2" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD $COMMON_OPTIONS "$HOST/$SVCPREFIX/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

date >> $LOGFILE
echo "" >> $LOGFILE

END=$(date +%s)
DIFF=$(( $END - $START ))

echo It took $DIFF seconds >> $LOGFILE
echo "" >> $LOGFILE
