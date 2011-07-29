#!/bin/sh

TARGET=${TARGET:-basin.isi.edu}
USERNAME=${USERNAME:-$(whoami)}
PASSWORD=${PASSWORD:-just4demo}

NAME=demo2
FILE=demo-template-2.html
QUERIES=(
'experimentID(experimentID;start;mice;principal;write%%20users)'
'mouseID(mouseID;experiment;cage;%%23cells;cell%%20type;dob;dos;start;mouse%%20label;mouse%%20strain;samples;treatments;observations;write%%20users)'
'sampleID(sampleID;experiment;mouse;sample%%20type;serum%%20sample%%20type;start;observations;performer;write%%20users)'
'observationID(observationID;experiment;mouse;start;comment;performer;write%%20users)'
'treatmentID(treatmentID;experiment;mouse;dose;drug;start;performer;write%%20users)'
)


COOKIEJAR=cookiejar.$$

cleanup()
{
    rm -f $COOKIEJAR
}

trap cleanup 0

URLCHARS=( '%' '(' ')' ';' )
URLCODES=( '%25' '%28' '%29' '%3B'  )

urlquote()
{
    local s="$1"

    for i in ${!URLCHARS[@]}
    do
	s="${s//${URLCHARS[$i]}/${URLCODES[$i]}}"
    done
    printf "%s\n" "$s"
}

mycurl()
{
    curl -b $COOKIEJAR -c $COOKIEJAR -k  "$@"
}

mycurl -d username="$USERNAME" -d password="$PASSWORD" "https://${TARGET}/webauthn/login"

mycurl -X DELETE "https://${TARGET}/tagfiler/file/name=${NAME}"

mycurl -T $FILE "https://${TARGET}/tagfiler/file/name=${NAME}"


for query in "${QUERIES[@]}"
do
    mycurl -X PUT "https://${TARGET}/tagfiler/tags/name=${NAME}(template%20query=$(urlquote "$query"))"
done

mycurl -d tag="template mode" -d value="embedded" -d action="put" "https://${TARGET}/tagfiler/tags/name=${NAME}"

