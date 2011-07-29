#!/bin/sh

COOKIEJAR=cookiejar.$$
USERNAME="${USERNAME:-$(whoami)}"
PASSWORD="${PASSWORD:-just4demo}"
TARGET=${TARGET:-basin.isi.edu}

URLCHARS=( '%' '\!' '\*' '(' ')' ';' ':' '@' '&' '=' '+' '$' ',' '/' '\?' '#' ' ')
URLCODES=( 25  21   2A   28  29  3B  3A  40  26  3D  2B  24  2C  2F  3F   23  20 )

urlquote()
{
    local s="$1"

    for i in ${!URLCHARS[@]}
    do
	s="${s//${URLCHARS[$i]}/%${URLCODES[$i]}}"
    done
    printf "%s\n" "$s"
}

mycurl()
{
    curl -b $COOKIEJAR -c $COOKIEJAR -k "$@"
}

newsubject()
{
    # idtag val [tag val]...
    echo newsubject: "$@"
    local uri="https://${TARGET}/tagfiler/subject/$(urlquote "$1")=$(urlquote "$2")"
    shift 2

    local sep='?'
    while [[ $# -gt 0 ]]
    do
	uri+="${sep}$(urlquote "$1")"
	sep='&'
	if [[ -n "$2" ]]
	then
	    uri+="=$(urlquote "$2")"
	fi
	shift 2
    done

    mycurl -X POST "$uri"
}

tagsubject()
{
    # idtag val [tag val]...
    local uri="https://${TARGET}/tagfiler/tags/$(urlquote "$1")=$(urlquote "$2")("
    shift 2

    local sep=''
    while [[ $# -gt 0 ]]
    do
	uri+="${sep}$(urlquote "$1")"
	sep=';'
	if [[ -n "$2" ]]
	then
	    uri+="=$(urlquote "$2")"
	fi
	shift 2
    done
    uri+=")"

    mycurl -X PUT "$uri"
}

tagsubjects()
{
    # querypath [tag val]...
    local uri

    uri="https://${TARGET}/tagfiler/tags/$1("
    shift

    local sep=''
    while [[ $# -gt 0 ]]
    do
	uri+="${sep}$(urlquote "$1")"
	sep=';'
	if [[ -n "$2" ]]
	then
	    uri+="=$(urlquote "$2")"
	fi
	shift 2
    done
    uri+=")?ignorenotfound=true"
    
    mycurl -s -X PUT "$uri"
}

cleanup()
{
    rm -f $COOKIEJAR
}

trap cleanup 0

cleanup

clearold()
{
    # DANGER! destroy any existing partially built demo data!  DANGER!
    mycurl -X DELETE "https://${TARGET}/tagfiler/subject/treatmentID" > /dev/null
    mycurl -X DELETE "https://${TARGET}/tagfiler/subject/mouseID" > /dev/null
    mycurl -X DELETE "https://${TARGET}/tagfiler/subject/experimentID" > /dev/null
    mycurl -X DELETE "https://${TARGET}/tagfiler/subject/sampleID" > /dev/null
    mycurl -X DELETE "https://${TARGET}/tagfiler/subject/observationID" > /dev/null
}


mycurl -d username="$USERNAME" -d password="$PASSWORD" https://${TARGET}/webauthn/login
clearold

IFS_save="$IFS"
declare -a p fields

f()
{
    local name="$1"
    for i in ${!fields[@]}
    do
	if [[ "${fields[$i]}" = "$name" ]]
	then
	    printf "%s\n" "${p[$i]}"
	fi
    done
}


    # observationID start comment

#################################### Experiment 1

mice=()

e1m()
{
    fields=(mouse cage label txdate ctype ncells treatp ttdate drug dose t0 t1 t2 t3 t4 t5 t6)
    local -a margs

    # blood samples t0 t1 t2 t3 t4 t5 t6
    # luciferase imaging t1 t2 t5 t6

    margs=( mouseID "$(f mouse)" start "$(f txdate)" cage "$(f cage)" "cell type" "$(f ctype)" "#cells" "$(f ncells)" "mouse label" "$(f label)"  )
    if [[ "$(f treatp)" = "y" ]]
    then
	newsubject treatmentID "$(f mouse)" start "$(f ttdate)" drug "$(f drug)" dose "$(f dose)" # create treatment record
	margs=( "${margs[@]}" treatments "$(f mouse)" )
    fi

    for obsv in {0..6}
    do
	sdate="$(f t$obsv)"
	if [[ -n "$sdate" ]] && [[ "${sdate:0:4}" != "died" ]]
	then
	    newsubject observationID "$(f mouse)/t$obsv" start "$sdate" "comment" "luciferase imaging"
	    margs=( "${margs[@]}" observations "$(f mouse)/t$obsv" )
	fi
    done

    for sample in {0..6}
    do
	dates=(2011-01-15 2011-01-27 2011-02-03 2011-02-04 2011-02-05 2011-02-10 2011-02-17)

	sdate="$(f t$sample)"
	if [[ -n "$sdate" ]]
	then
	    if [[ "${sdate:0:4}" = "died" ]]
	    then
		newsubject observationID "$(f mouse)/t$sample" start "${dates[$sample]}" comment "$sdate"
		margs=( "${margs[@]}" observations "$(f mouse)/t$sample" )
	    else
		newsubject sampleID "$(f mouse)/t$sample" start "$sdate" "sample type" "serum"
		margs=( "${margs[@]}" samples "$(f mouse)/t$sample" )
	    fi
	fi
    done

    newsubject "${margs[@]}" # create mouse record
    mice=( "${mice[@]}" "$(f mouse)" )

    tagsubjects "mouseID=$(urlquote "$(f mouse)")(treatments)/" mouse "$(f mouse)"
    tagsubjects "mouseID=$(urlquote "$(f mouse)")(samples)/" mouse "$(f mouse)"
    tagsubjects "mouseID=$(urlquote "$(f mouse)")(observations)/" mouse "$(f mouse)"
}

e1()
{

IFS=","
while read -a p
do
    IFS="${IFS_save}"
    e1m "${p[@]}"
    IFS=","
done <<EOF
PSOC#51,1,1,2011-01-20,Arf-/-,0.15e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#52,1,2,2011-01-20,Arf-/-,0.15e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#53,1,3,2011-01-20,Arf-/-,0.15e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#54,1,4,2011-01-20,Arf-/-,0.15e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,died before sampling,
PSOC#55,1,5,2011-01-20,Arf-/-,0.15e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,died before sampling,
PSOC#56,2,6,2011-01-20,Arf-/-,0.15e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,died before sampling,
PSOC#57,2,7,2011-01-20,Arf-/-,0.3e6,n,,,,1/15/2011,1/27/2011,died of lymphoma 2011-02-02,,,,
PSOC#58,2,8,2011-01-20,Arf-/-,0.3e6,n,,,,1/15/2011,1/27/2011,died of lymphoma 2011-02-02,,,,
PSOC#59,2,9,2011-01-20,Arf-/-,0.3e6,n,,,,1/15/2011,1/27/2011,died of lymphoma 2011-02-02,,,,
PSOC#60,2,10,2011-01-20,Arf-/-,0.3e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,died of lymphoma 2011-02-02,,,,
PSOC#61,3,11,2011-01-20,Arf-/-,0.3e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,died of lymphoma 2011-02-02,,,,
PSOC#62,3,12,2011-01-20,Arf-/-,0.3e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,died of lymphoma 2011-02-02,,,,
PSOC#63,3,13,2011-01-20,p53-/-,0.2e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#64,3,14,2011-01-20,p53-/-,0.2e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#65,3,15,2011-01-20,p53-/-,0.2e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#66,4,16,2011-01-20,p53-/-,0.2e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#67,4,17,2011-01-20,p53-/-,0.2e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#68,4,18,2011-01-20,p53-/-,0.2e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#69,4,19,2011-01-20,p53-/-,0.4e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#70,4,20,2011-01-20,p53-/-,0.4e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#71,5,21,2011-01-20,p53-/-,0.4e6,n,,,,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#72,5,22,2011-01-20,p53-/-,0.4e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#73,5,23,2011-01-20,p53-/-,0.4e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
PSOC#74,5,24,2011-01-20,p53-/-,0.4e6,y,3.2.2011,doxorubicin,10,1/15/2011,1/27/2011,2/3/2011,2/4/2011,2/5/2011,2011-02-11,2011-02-17
EOF
IFS="${IFS_save}"

declare -a args

args=(experimentID "PSOC serum 2011-01-11" start "2011-01-11" )
shift 2
for mouse in "${mice[@]}"
do
    args=( "${args[@]}" mice "$mouse" )
done
newsubject "${args[@]}" # create experiment record
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-01-11")(mice)/" experiment "PSOC serum 2011-01-11"
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-01-11")(mice)/(treatments)/" experiment "PSOC serum 2011-01-11"
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-01-11")(mice)/(samples)/" experiment "PSOC serum 2011-01-11"
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-01-11")(mice)/(observations)/" experiment "PSOC serum 2011-01-11"

}

e1

#################################### Experiment 2

mice=()

#experiment "PSOC serum 2011-03-25" 2011-03-25

e2m()
{
    fields=(mouse cage label txdate mtype mvend dob ctype ncells treatp ttdate drug dose t0 t1 t2 t4 t5 dod)

    # blood samples t0 t1 t2 t4 t5
    # luciferase imaging t1 t2 t4 t5

    margs=( mouseID "$(f mouse)" start "$(f txdate)" cage "$(f cage)" "cell type" "$(f ctype)" "#cells" "$(f ncells)" "mouse label" "$(f label)" "mouse strain" "$(f mtype)" dob "$(f dob)" )
    if [[ "$(f treatp)" = "y" ]]
    then
	newsubject treatmentID "$(f mouse)" start "$(f ttdate)" drug "$(f drug)" dose "$(f dose)" # create treatment record
	margs=( "${margs[@]}" treatments "$(f mouse)" )
    fi

    for obsv in 1 2  4 5
    do
	sdate="$(f t$obsv)"
	if [[ -n "$sdate" ]]
	then
	    case "$sdate" in
		*dead*|*final*)
		    :
		    ;;
		*)
		    newsubject observationID "$(f mouse)/t$obsv" start "$sdate" "comment" "luciferase imaging"
		    margs=( "${margs[@]}" observations "$(f mouse)/t$obsv" )
		    ;;
	    esac
	fi
    done

    for sample in 0 1 2  4 5
    do
	dates=(2011-03-24 2011-03-31 2011-04-7 '' 2011-04-14 2011-04-21)

	sdate="$(f t$sample)"
	if [[ -n "$sdate" ]]
	then
	    case "$sdate" in
		*dead*)
		    newsubject observationID "$(f mouse)/t$sample" start "${dates[$sample]}" comment "$sdate"
		    margs=( "${margs[@]}" observations "$(f mouse)/t$sample" )
		    ;;
		*bleed*)
		    bdate=${sdate#final bleed }
		    newsubject sampleID "$(f mouse)/t$sample" start "$bdate" "sample type" "serum" "serum sample type" "terminal"
		    margs=( "${margs[@]}" samples "$(f mouse)/t$sample" dos "$bdate" )
		    ;;
		*)
		    newsubject sampleID "$(f mouse)/t$sample" start "$sdate" "sample type" "serum"
		    margs=( "${margs[@]}" samples "$(f mouse)/t$sample" )
		    ;;
	    esac
	fi
    done

    newsubject "${margs[@]}" # create mouse record
    mice=( "${mice[@]}" "$(f mouse)" )

    tagsubjects "mouseID=$(urlquote "$(f mouse)")(treatments)/" mouse "$(f mouse)"
    tagsubjects "mouseID=$(urlquote "$(f mouse)")(samples)/" mouse "$(f mouse)"
    tagsubjects "mouseID=$(urlquote "$(f mouse)")(observations)/" mouse "$(f mouse)"
}

e2()
{

IFS=","
while read -a p
do
    IFS="${IFS_save}"
    e2m "${p[@]}"
    IFS=","
done <<EOF
PSOC#75,1,1,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.1e6,n,,,,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#76,1,2,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.1e6,n,,,,3/24/2011,3/31/2011,4/7/2011,found dead 2011-4-12,,2011-4-12
PSOC#77,1,3,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.1e6,n,,,,3/24/2011,3/31/2011,4/7/2011,found dead 2011-4-12,,2011-4-12
PSOC#78,1,4,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.1e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#79,1,5,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.1e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#80,2,6,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.1e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#81,2,7,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.3e6,n,,,,3/24/2011,3/31/2011,4/7/2011,found dead 2011-4-11,,2011-4-11
PSOC#82,2,8,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.3e6,n,,,,3/24/2011,3/31/2011,4/7/2011,found dead 2011-4-12,,2011-4-12
PSOC#83,2,9,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.3e6,n,,,,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#84,2,10,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.3e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,found dead 2011-4-12,,2011-4-12
PSOC#85,3,11,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.3e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,final bleed 2011-4-15,,2011-4-15
PSOC#86,3,12,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc+,0.3e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#87,3,13,2011-03-25,C57B6,,12/30/2010,control,0,n,,,,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#88,3,14,2011-03-25,C57B6,,12/30/2010,control,0,n,,,,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#89,3,15,2011-03-25,C57B6,,12/30/2010,control,0,n,,,,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#90,4,16,2011-03-25,C57B6,,12/30/2010,control,0,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#91,4,17,2011-03-25,C57B6,,12/30/2010,control,0,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#92,4,18,2011-03-25,C57B6,,12/30/2010,control,0,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,2011-4-14,2011-4-21,
PSOC#93,4,19,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc-,0.1e6,n,,,,3/24/2011,3/31/2011,4/7/2011,found dead 2011-4-12,,2011-4-12
PSOC#94,4,20,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc-,0.1e6,n,,,,3/24/2011,3/31/2011,4/7/2011,final bleed 2011-4-15,,2011-4-15
PSOC#95,5,21,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc-,0.1e6,n,,,,3/24/2011,3/31/2011,4/7/2011,found dead 2011-4-11,,2011-4-11
PSOC#96,5,22,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc-,0.1e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,final bleed 2011-4-15,,2011-4-15
PSOC#97,5,23,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc-,0.1e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,final bleed 2011-4-15,,2011-4-16
PSOC#98,5,24,2011-03-25,C57B6,,12/30/2010,Arf-/- Luc-,0.1e6,y,2011-4-7,doxorubicin,10,3/24/2011,3/31/2011,4/7/2011,final bleed 2011-4-15,,2011-4-16
EOF
IFS="${IFS_save}"

declare -a args

args=(experimentID "PSOC serum 2011-03-25" start "2011-03-25" )
shift 2
for mouse in "${mice[@]}"
do
    args=( "${args[@]}" mice "$mouse" )
done
newsubject "${args[@]}" # create experiment record
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-03-25")(mice)/" experiment "PSOC serum 2011-03-25"
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-03-25")(mice)/(treatments)/" experiment "PSOC serum 2011-03-25"
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-03-25")(mice)/(samples)/" experiment "PSOC serum 2011-03-25"
tagsubjects "experimentID=$(urlquote "PSOC serum 2011-03-25")(mice)/(observations)/" experiment "PSOC serum 2011-03-25"

}

e2



#################################### Experiment 3

mice=()

#experiment "PSOC serum 2010-09-15" 2010-09-15

e3m()
{
    fields=(mouse junk txdate ctype ncells treatp ttdate drug dose t0 t1 t2 t3)

    # blood samples t0 t1 t2 t3 some annotated (FB)

    margs=( mouseID "$(f mouse)" )

    [[ -n "$(f start)" ]] && margs=( "${margs[@]}" start "$(f txdate)" )
    [[ -n "$(f ctype)" ]] && margs=( "${margs[@]}" "cell type" "$(f ctype)" )
    [[ -n "$(f ncells)" ]] && margs=( "${margs[@]}" "#cells" "$(f ncells)" )

    if [[ "$(f treatp)" = "y" ]]
    then
	newsubject treatmentID "$(f mouse)" start "$(f ttdate)" drug "$(f drug)" dose "$(f dose)" # create treatment record
	margs=( "${margs[@]}" treatments "$(f mouse)" )
    fi

    for sample in 0 1 2 3
    do
	sdate="$(f t$sample)"
	if [[ -n "$sdate" ]]
	then
	    case "$sdate" in
		*dead*|*died*)
		    ddate=$(echo "$sdate" | sed -e "s/[^0-9]*\([-./0-9]\+\)[^0-9]*/\1/")
		    newsubject observationID "$(f mouse)/t$sample" start "$ddate" comment "$sdate"
		    margs=( "${margs[@]}" observations "$(f mouse)/t$sample" )
		    ;;
		*FB*)
		    bdate=$(echo "$sdate" | sed -e "s/[^0-9]*\([-./0-9]\+\)[^0-9].*/\1/")
		    newsubject sampleID "$(f mouse)/t$sample" start "$bdate" "sample type" "serum" "serum sample type" "terminal"
		    margs=( "${margs[@]}" samples "$(f mouse)/t$sample" dos "$bdate" )
		    ;;
		*)
		    newsubject sampleID "$(f mouse)/t$sample" start "$sdate" "sample type" "serum"
		    margs=( "${margs[@]}" samples "$(f mouse)/t$sample" )
		    ;;
	    esac
	fi
    done

    newsubject "${margs[@]}" # create mouse record
    mice=( "${mice[@]}" "$(f mouse)" )

    tagsubjects "mouseID=$(urlquote "$(f mouse)")(treatments)/" mouse "$(f mouse)"
    tagsubjects "mouseID=$(urlquote "$(f mouse)")(samples)/" mouse "$(f mouse)"
    tagsubjects "mouseID=$(urlquote "$(f mouse)")(observations)/" mouse "$(f mouse)"
}

IFS=","
while read -a p
do
    IFS="${IFS_save}"
    e3m "${p[@]}"
    IFS=","
done <<EOF
PSOC#1,,9/17/2010,Arf-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,
PSOC#2,,9/17/2010,Arf-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,
PSOC#3,,9/17/2010,Arf-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,
PSOC#4,,9/17/2010,Arf-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,
PSOC#5,,9/17/2010,Arf-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,
PSOC#6,,9/17/2010,Arf-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,
PSOC#7,,9/17/2010,Arf-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,
PSOC#8,,9/17/2010,Arf-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,
PSOC#9,,9/17/2010,Arf-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,
PSOC#10,,9/17/2010,Arf-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,
PSOC#11,,9/17/2010,p53-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,FB 2010-10-5
PSOC#12,,9/17/2010,p53-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,FB 2010-10-5
PSOC#13,,9/17/2010,p53-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,dead 2010-10-4
PSOC#14,,9/17/2010,p53-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,FB 2010-10-5
PSOC#15,,9/17/2010,p53-/-,1e6,n,,,,9/16/2010,9/23/2010,9/30/2010,FB 2010-10-5
PSOC#16,,9/17/2010,p53-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,dead 2010-10-4
PSOC#17,,9/17/2010,p53-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,dead 2010-10-4
PSOC#18,,9/17/2010,p53-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,FB 2010-10-5
PSOC#19,,9/17/2010,p53-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,FB 2010-10-5
PSOC#20,,9/17/2010,p53-/-,1e6,y,10/1/2010,doxorubicin,10,9/16/2010,9/23/2010,9/30/2010,dead 2010-10-4
PSOC#21,,,,,,,,,9/16/2010 (FB),,,
PSOC#22,,,,,,,,,9/16/2010 (FB),,,
PSOC#23,,,,,,,,,9/16/2010 (FB),,,
PSOC#24,,9/17/2010,Arf-/-,1e6,n,,,,,9/23/2010 (FB),,
PSOC#25,,9/17/2010,Arf-/-,1e6,n,,,,,9/23/2010 (FB),,
PSOC#26,,9/17/2010,Arf-/-,1e6,n,,,,,9/23/2010 (FB),,
PSOC#27,,9/17/2010,Arf-/-,1e6,n,,,,,,9/30/2010 (FB),
PSOC#28,,9/17/2010,Arf-/-,1e6,n,,,,,,9/30/2010 (FB),
PSOC#29,1,9/17/2010,Arf-/-,1e6,n,,,,,,died 9/30/2010 before sampling,
PSOC#30,2,9/17/2010,Arf-/-,1e6,n,,,,,,9/30/2010 (FB),
PSOC#31,3,9/17/2010,Arf-/-,1e6,n,,,,,,,died 9/30/2010
PSOC#32,4,9/17/2010,Arf-/-,1e6,n,,,,,,,died 9/30/2010
PSOC#33,5,9/17/2010,Arf-/-,1e6,n,,,,,,,FB 2010-10-5
PSOC#34,1,9/17/2010,Arf-/-,1e6,n,,,,,,,FB 2010-10-5
PSOC#35,2,9/17/2010,Arf-/-,1e6,n,,,,,,,died 2010-10-2 no sampling
PSOC#36,3,,,,,,,,9/16/2010 (FB),,,
PSOC#37,4,,,,,,,,9/16/2010 (FB),,,
PSOC#38,5,,,,,,,,9/16/2010 (FB),,,
PSOC#39,,9/17/2010,p53-/-,1e6,n,,,,,9/23/2010 (FB),,
PSOC#40,,9/17/2010,p53-/-,1e6,n,,,,,9/23/2010 (FB),,
PSOC#41,,9/17/2010,p53-/-,1e6,n,,,,,9/23/2010 (FB),,
PSOC#42,,9/17/2010,p53-/-,1e6,n,,,,,,9/30/2010 (FB),
PSOC#43,,9/17/2010,p53-/-,1e6,n,,,,,,9/30/2010 (FB),
PSOC#44,,9/17/2010,p53-/-,1e6,n,,,,,,9/30/2010 (FB),
PSOC#45,,9/17/2010,p53-/-,1e6,n,,,,,,,dead 2010-10-5
PSOC#46,,9/17/2010,p53-/-,1e6,n,,,,,,,dead 2010-10-4
PSOC#47,,9/17/2010,p53-/-,1e6,n,,,,,,,FB 2010-10-5
PSOC#48,,9/17/2010,p53-/-,1e6,n,,,,,,,dead 2010-10-4
PSOC#49,,9/17/2010,p53-/-,1e6,n,,,,,,,FB 2010-10-5
PSOC#50,,9/17/2010,p53-/-,1e6,n,,,,,,,dead 2010-10-4
EOF
IFS="${IFS_save}"

declare -a args

args=(experimentID "PSOC serum 2010-09-15" start 2010-09-15  )
shift 2
for mouse in "${mice[@]}"
do
    args=( "${args[@]}" mice "$mouse" )
done
newsubject "${args[@]}" # create experiment record
tagsubjects "experimentID=$(urlquote "PSOC serum 2010-09-15")(mice)/" experiment "PSOC serum 2010-09-15"
tagsubjects "experimentID=$(urlquote "PSOC serum 2010-09-15")(mice)/(treatments)/" experiment "PSOC serum 2010-09-15"
tagsubjects "experimentID=$(urlquote "PSOC serum 2010-09-15")(mice)/(samples)/" experiment "PSOC serum 2010-09-15"
tagsubjects "experimentID=$(urlquote "PSOC serum 2010-09-15")(mice)/(observations)/" experiment "PSOC serum 2010-09-15"


mycurl -d action=logout https://${TARGET}/webauthn/logout

