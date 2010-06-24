#!/bin/sh

HOST=http://aspc.isi.edu
AUTHENTICATION=serban:just4demo
AUTHENTICATION_METHOD=digest

LOGFILE=psoc.log
TEMPFILE=psocTemp
DATASET1=Spectrophotometry
DATASET2=Retinoblastoma
FILE=/home/serban/Temp/gigafile
URL=http://www.yahoo.com
TAG1=Location
TAG2=Color
DATASET1_TAG1_VALUE1=Los%20Angeles
DATASET1_TAG1_VALUE2=San%20Francisco
DATASET1_TAG2_VALUE=Green
DATASET2_TAG1_VALUE1=Los%20Angeles
DATASET2_TAG1_VALUE2=San%20Diego
DATASET2_TAG2_VALUE=Green

date > $LOGFILE
echo "" >> $LOGFILE

# Tags Actions

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "tag-1=$TAG1&type-1=text&multivalue-1=true&restricted-1=true&action=add" "$HOST/tagfiler/tagdef" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=ConfirmDelete" "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with PUT" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X PUT "$HOST/tagfiler/tagdef/$TAG1?typestr=text&multivalue=true&restricted=false" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with DELETE" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE  "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG1\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "tag-1=$TAG1&type-1=text&multivalue-1=true&restricted-1=true&action=add" "$HOST/tagfiler/tagdef" >> $LOGFILE

echo "List \"$TAG1\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$TAG2\" tag with POST" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "tag-1=$TAG2&type-1=text&multivalue-1=false&restricted-1=false&action=add" "$HOST/tagfiler/tagdef" >> $LOGFILE

echo "List \"$TAG2\" tag" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef/$TAG2" >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

# Dataset Actions

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET1\" dataset with POST"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -F "file=@$FILE" "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with url POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=put&url=$URL" "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with file POST"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -F "file=@$FILE" "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Get/Download \"$DATASET1\" dataset"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -o "$TEMPFILE" -X GET "$HOST/tagfiler/file/$DATASET1"
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
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=ConfirmDelete" "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -T "$FILE" "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Update \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -T "$FILE" "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Get/Download \"$DATASET1\" dataset"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -o "$TEMPFILE" -X GET "$HOST/tagfiler/file/$DATASET1"
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
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

# Adding Dataset Tags

echo "Define \"$DATASET1\" dataset with PUT"  >> $LOGFILE
date >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -T "$FILE" "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE
date >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Define \"$DATASET2\" dataset with url POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=put&url=$URL" "$HOST/tagfiler/file/$DATASET2" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG1\" tag to dataset \"$DATASET1\" with values \"$DATASET1_TAG1_VALUE1\" and \"$DATASET1_TAG1_VALUE2\" using POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE1" "$HOST/tagfiler/tags/$DATASET1" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET1_TAG1_VALUE2" "$HOST/tagfiler/tags/$DATASET1" >> $LOGFILE

echo "Fetch \"$TAG1\" tag of dataset \"$DATASET1\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET1/$TAG1"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG2\" tag to dataset \"$DATASET1\" with value \"$DATASET1_TAG2_VALUE\" using PUT"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X PUT "$HOST/tagfiler/tags/$DATASET1/$TAG2=$DATASET1_TAG2_VALUE" >> $LOGFILE

echo "Fetch \"$TAG2\" tag of dataset \"$DATASET1\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET1/$TAG2"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG1\" tag to dataset \"$DATASET2\" with values \"$DATASET2_TAG1_VALUE1\" and \"$DATASET2_TAG1_VALUE2\" using POST"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE1" "$HOST/tagfiler/tags/$DATASET2" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "action=put&set-$TAG1=true&val-$TAG1=$DATASET2_TAG1_VALUE2" "$HOST/tagfiler/tags/$DATASET2" >> $LOGFILE

echo "Fetch \"$TAG1\" tag of dataset \"$DATASET2\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET2/$TAG1"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Add \"$TAG2\" tag to dataset \"$DATASET2\" with value \"$DATASET2_TAG2_VALUE\" using PUT"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X PUT "$HOST/tagfiler/tags/$DATASET2/$TAG2=$DATASET2_TAG2_VALUE" >> $LOGFILE

echo "Fetch \"$TAG2\" tag of dataset \"$DATASET2\""  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET2/$TAG2"  >> $LOGFILE
echo -e "\n" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

# Queries

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\" OR \"$TAG1\" == \"$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1,$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET1_TAG1_VALUE1\" AND \"$TAG1\" == \"$DATASET1_TAG1_VALUE2\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET1_TAG1_VALUE1;$TAG1=$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Query for \"$TAG1\" == \"$DATASET2_TAG1_VALUE2\" AND \"$TAG2\" == \"$DATASET1_TAG2_VALUE\"" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -k -H "Accept: text/uri-list" -X GET "$HOST/tagfiler/query/$TAG1=$DATASET2_TAG1_VALUE2;$TAG2=$DATASET1_TAG2_VALUE" >> $LOGFILE
echo "" >> $LOGFILE

# Deleting tags from datasets

echo "Delete value \"$DATASET1_TAG1_VALUE1\" of \"$TAG1\" tag from dataset \"$DATASET1\" with POST" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -d "tag=$TAG1&action=delete&value=$DATASET1_TAG1_VALUE1" "$HOST/tagfiler/tags/$DATASET1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete value \"$DATASET1_TAG1_VALUE2\" of \"$TAG1\" tag from dataset \"$DATASET1\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE "$HOST/tagfiler/tags/$DATASET1/$TAG1=$DATASET1_TAG1_VALUE2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag from dataset \"$DATASET1\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE "$HOST/tagfiler/tags/$DATASET1/$TAG2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET1\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET1"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag from dataset \"$DATASET2\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE "$HOST/tagfiler/tags/$DATASET2/$TAG1" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag from dataset \"$DATASET2\" with DELETE" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE "$HOST/tagfiler/tags/$DATASET2/$TAG2" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch dataset \"$DATASET2\" tags"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/tags/$DATASET2"  | xsltproc --html dataset.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG1\" tag with DELETE" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE  "$HOST/tagfiler/tagdef/$TAG1" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$TAG2\" tag with DELETE" >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE  "$HOST/tagfiler/tagdef/$TAG2" >> $LOGFILE

echo "List tag definitions" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S "$HOST/tagfiler/tagdef" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$DATASET1\" dataset with DELETE"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE "$HOST/tagfiler/file/$DATASET1" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

echo "Delete \"$DATASET2\" dataset with DELETE"  >> $LOGFILE
echo "" >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S -X DELETE "$HOST/tagfiler/file/$DATASET2" >> $LOGFILE

echo "Fetch the list of datasets"  >> $LOGFILE
curl -u $AUTHENTICATION --$AUTHENTICATION_METHOD -s -S  "$HOST/tagfiler/file" | xsltproc --html tagdef.xslt - | grep -v "<?xml" | grep -v "^$" >> $LOGFILE
echo "" >> $LOGFILE

date >> $LOGFILE
echo "" >> $LOGFILE


