#!/bin/sh

rm -f *.log

for (( i = 1; i <= $1; i++ ))
do
	java -cp $JAR_LIB edu.isi.misd.tagfiler.test.TagfilerClient -h $HOST -o $INPUT -u $USER -a 4194304 -c 4 -e -p $PASSWORD >$i.log 2>&1 &
done

wait


