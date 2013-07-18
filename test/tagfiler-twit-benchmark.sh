#!/bin/sh

## 
## This is the schema for the data under test
## 
## the first tagdef name MUST be the primary key for subjects being loaded
## the catalog MUST NOT have subjects using this tag other than those managed by this test
##
## it is OK to have additional tagdefs here in positions 1..N that end up unused
tagdefs=(
    "tweet"
    "user"
    "generator"
    "posted_time"
    "body"
    "retweet_of"
    "written_by"
    "generated_by"
    "hashtag_mention"
    "user_mention"
    "url_mention"
)

##
## This is the set of tagdefs to create, one per name provided above at the same respective position
## put a blank string '' if using a built-in tagdef that should NOT be created
##
tagdef_opts=(
    "dbtype=int8&unique=true&readpolicy=subject&writepolicy=subject"
    "dbtype=int8&unique=true&readpolicy=subject&writepolicy=subject"
    "dbtype=int8&unique=true&readpolicy=subject&writepolicy=subject"
    "dbtype=timestamptz&readpolicy=subject&writepolicy=subject"
    "dbtype=text&readpolicy=subject&writepolicy=subject"
    "dbtype=int8&tagref=tweet&soft=true&readpolicy=subject&writepolicy=subject"
    "dbtype=int8&tagref=user&soft=true&readpolicy=subject&writepolicy=subject"
    "dbtype=int8&tagref=generator&soft=true&readpolicy=subject&writepolicy=subject"
    "dbtype=text&multivalue=true&readpolicy=subject&writepolicy=subject"
    "dbtype=int8&tagref=user&soft=true&multivalue=true&readpolicy=subject&writepolicy=subject"
    "dbtype=text&multivalue=true&readpolicy=subject&writepolicy=subject"
)

# an ordered, space-separated list of column numbers in the input file
#REST_COLS="${REST_COLS:-0 6 3 5 4 7 8 9 10}" # default to twit-t9 extract
REST_COLS="${REST_COLS:-0 3 4 8}"  # default to twit-t4 extract
REST_COLS=( ${REST_COLS} )

# the integer number of input rows to add to graph per test cycle
TEST_STRIDE="${TEST_STRIDE:-1}"

# the integer stride number to start at (for restarting interrupted tests)
FIRST_STRIDE="${FIRST_STRIDE:-0}"

# the ordered, space-separated list of integer measurement sizes to perform per test cycle
TEST_SIZES="${TEST_SIZES:-1}"
TEST_SIZES=( ${TEST_SIZES} )

# the integer number of test measurements at each stride and size
TEST_CYCLES="${TEST_CYCLES:-1}"

# non-empty string to enable per-test DB analyze maintenance
TEST_ANALYZE="${TEST_ANALYZE:-}"

username=$1
password=$2
command=$3

API="$4"
# "https://${host}/tagfiler"
base_api="${API%/catalog/*}"

host="${API%/tagfiler/catalog/*}"
host="${host#http*://}"

tempfile=$(mktemp)
tempfile2=$(mktemp)
tempfile3=$(mktemp)
cookie=$(mktemp)

logfile=$(mktemp)

cleanup()
{
    rm -f "$tempfile" "$logfile" "$tempfile2" "$tempfile3" "$cookie"
}

trap cleanup 0

mycurl()
{
    local url="$1"
    shift
    truncate -s 0 $logfile

    case "$url" in
	/session)
	    url="${base_api}${url}"
	    ;;
	*)
	    url="${API}${url}"
	    ;;
    esac

    curl -b $cookie -c $cookie -k -w "%{http_code}\n" -s "$@" "${url}"
}

error()
{
    cat >&2 <<EOF
$0: $@
$(cat $logfile)
EOF
    exit 1
}

warning()
{
    cat >&2 <<EOF
warning: $@
$(cat $logfile)
EOF
}

help()
{
    cat >&2 <<EOF
$0 <username> <password> <command> <catalog>

Where command is one of:

   help      --> this text
   create    --> create tagdefs
   runtest   --> test loading/getting/deleting data, print perf trace to stdout
   unload    --> remove test data
   delete    --> delete tagdefs

Catalog is a URL such as https://hostname/tagfiler/catalog/7 to which this
script can append API URL fragments to construct test resources.

Load takes environment parameters:

   LOAD_FILE    --> file with CSV data to load

   REST_COLS    --> ordered list of column numbers as present in LOAD_FILE

   TEST_STRIDE  --> the number of data rows added to the graph per test stride (default 1)
   FIRST_STRIDE --> restart on this stride (default 0)

   TEST_SIZES   --> the numbers of data rows added/fetched/deleted per test measurement (default 1)

   TEST_CYCLES  --> number of times to repeat testing of each test size for each stride (default 1)

   TEST_ANALYZE --> non-empty to enable expensive DB maintenance between tests (default empty/disabled)

Host defaults to localhost if absent.

The REST_COLS is an ordered list of integers identifying the subset of
columns used in the LOAD_FILE, drawn from this list of available test columns:

$(for i in ${!tagdefs[@]}
  do
     printf "%4.1d: %s\n" $i "${tagdefs[$i]}"
  done)

EOF
    exit 1
}

[[ -n "$command" ]] || help

[[ "${TEST_STRIDE}" -gt 0 ]] || error stride size "${TEST_STRIDE}" must be greater than 0

[[ "${TEST_CYCLES}" -gt 0 ]] || error test cycle count "${TEST_CYCLES}" must be greater than 0

[[ -n "$API" ]] || error catalog URL required

REST_COL_NAMES=''
sep=''
for c in ${REST_COLS[@]}
do
    [[ "$c" -ge 0 ]] || error rest column "$c" must be greater or equal to 0
    [[ "$c" -lt ${#tagdefs[@]} ]] || error rest column "$c" must be less than schema column count ${#tagdefs[@]}
    REST_COL_NAMES+="${sep}${tagdefs[$c]}"
    sep=";"
done

[[ "${#TEST_SIZES[@]}" -gt 0 ]] || error at least one size integer required for TEST_SIZES
for s in ${TEST_SIZES[@]}
do
    [[ "$s" -ge 1 ]] || error test size "$s" must be greater or equal to 1
    [[ "$s" -le "${TEST_STRIDE}" ]] || error test size "$s" must be less or equal to stride size "${TEST_STRIDE}"
done

create()
{
    for i in ${!tagdefs[@]}
    do
	if [[ -n "${tagdef_opts[$i]}" ]]
	then
	    status=$(mycurl "/tagdef/${tagdefs[$i]}?${tagdef_opts[$i]}" -X PUT -o $logfile)
	    [[ "$status" = 201 ]] || warning got "$status" creating "tagdef=${tagdefs[$i]}"
	fi
    done
}

delete()
{
    for i in ${!tagdefs[@]}
    do
	if [[ -n "${tagdef_opts[$i]}" ]]
	then
	    status=$(mycurl "/tagdef/${tagdefs[$i]}" -X DELETE -o $logfile)
	    [[ "$status" = 204 ]] || warning got "$status" deleting "tagdef=${tagdefs[$i]}"
	fi
    done
}

datems()
{
    # gets seconds since epoch and nanoseconds then scales down by 10^6 to get milliseconds
    echo $(( $(date +%s%N) / 1000000 ))
}

ms2sec()
{
    # converts milliseconds integer to seconds floating point decimal string
    sec=$(( $1 / 1000 ))
    ms=$(( $1 % 1000 ))
    printf "%d.%3.3d\n" $sec $ms
}

runtest()
{
    [[ -r "${LOAD_FILE}" ]] || error cannot read LOAD_FILE "\"${LOAD_FILE}\""

    total_lines=$(wc -l < "${LOAD_FILE}")

    [[ "${total_lines}" -gt "${TEST_STRIDE}" ]] || error input file record count ${total_lines} must be greater than TEST_STRIDE size ${TEST_STRIDE}

    stride_count=$(( ${total_lines} / ${TEST_STRIDE} ))

    [[ "${FIRST_STRIDE}" -lt ${stride_count} ]] || error FIRST_STRIDE "${FIRST_STRIDE}" must be less than stride count ${stride_count} determined from LOAD_FILE

    status=$(mycurl "/maintenance?analyze=true" -X PUT -o $logfile)
    [[ "$status" = 204 ]] || error could not perform initial maintenance


    # print CSV header
    printf "hostname,graphsize"
    for test_size in ${TEST_SIZES[@]}
    do
	printf ",PUT ${test_size},GET ${test_size},DEL ${test_size}"
    done
    printf "\n"

    stride=${FIRST_STRIDE}
    first_byte=''

    while [[ $stride -lt ${stride_count} ]]
    do
	# get stride data into a temp file
	if [[ -n "${first_byte}" ]]
	then
	    # efficiently jump to offset found by last stride iteration
	    # first_byte is zero-based length of content we are skipping
	    # tail -c +N expects 1-based byte position, so add 1
	    tail -c +$(( 1 + ${first_byte} )) < ${LOAD_FILE} | head -n ${TEST_STRIDE} > $tempfile2
	    first_byte=$(( ${first_byte} + $(wc -c < $tempfile2) ))
	else
	    tail -n +$(( 1 + ${stride} * ${TEST_STRIDE} )) < ${LOAD_FILE} | head -n ${TEST_STRIDE} > $tempfile2
	    first_byte=$(wc -c < $tempfile2)
	fi

	length=$(wc -l < $tempfile2)
	[[ $length -eq ${TEST_STRIDE} ]] || error stride ${stride} file has ${length} rows instead of expected ${TEST_STRIDE}

	# get current top of graph so we can reset between tests
	status=$(mycurl "/subject/id(id)id:desc:?limit=1" -H "Accept: text/csv" -o $logfile)
	[[ "$status" = 200 ]] || error could not determine maximum subject ID prior to load cycle
	prev_max_id=$(cat $logfile)

	cycle=0

	while [[ $cycle -lt ${TEST_CYCLES} ]]
	do
	    # print CSV keys
	    printf "${host},$(( $stride * ${TEST_STRIDE} ))"

	    for test_size in ${TEST_SIZES[@]}
	    do
		# get test data into a temp file
		head -n ${test_size} < $tempfile2 > $tempfile3
		length=$(wc -l < $tempfile3)
		[[ $length -eq ${test_size} ]] || error stride ${stride} "test size" ${test_size} file has ${length} rows 

		if [[ -n "${TEST_ANALYZE}" ]]
		then
		    status=$(mycurl "/maintenance?analyze=true" -X PUT -o $logfile)
		    [[ "$status" = 204 ]] || error could not perform incremental maintenance
		fi

		# do PUT test
		t0=$(datems)

		status=$(mycurl "/subject/${tagdefs[0]}(${REST_COL_NAMES})" -H "Content-Type: text/csv" -T $tempfile3 -X POST -o $logfile)
		[[ "$status" = 204 ]] || error got status "$status" bulk putting test data
		t1=$(datems)
		printf ",$(ms2sec $(( $t1 - $t0 )) )"

		if [[ -n "${TEST_ANALYZE}" ]]
		then
		    status=$(mycurl "/maintenance?analyze=true" -X PUT -o $logfile)
		    [[ "$status" = 204 ]] || error could not perform incremental maintenance
		fi

		idpreds="id:gt:${prev_max_id}"

		# do GET test
		t0=$(datems)
		status=$(mycurl "/subject/${tagdefs[0]};${idpreds}(${REST_COL_NAMES})?limit=${test_size}" -H "Accept: text/csv" -o $logfile)
		[[ "$status" = 200 ]] || error got status "$status" bulk getting batch data
		t1=$(datems)
		length=$(wc -l < $logfile)
		[[ $length -eq ${test_size} ]] || error got $length results instead of ${test_size} doing bulk get

		printf ",$(ms2sec $(( $t1 - $t0 )) )"

		# do DELETE test
		t0=$(datems)
		status=$(mycurl "/subject/${tagdefs[0]};id:gt:${prev_max_id}" -X DELETE -o $logfile)
		[[ "$status" = 204 ]] || error got status "$status" bulk deleting batch data
		t1=$(datems)
		printf ",$(ms2sec $(( $t1 - $t0 )) )"

		if [[ -n "${TEST_ANALYZE}" ]]
		then
		    status=$(mycurl "/maintenance?analyze=true" -X PUT -o $logfile)
		    [[ "$status" = 204 ]] || error could not perform incremental maintenance
		fi

	    done

	    printf "\n"

	    cycle=$(( $cycle + 1 ))
	done

	# insert current stride so graph grows for next test round
	status=$(mycurl "/subject/${tagdefs[0]}(${REST_COL_NAMES})" -H "Content-Type: text/csv" -T $tempfile2 -X POST -o $logfile)
	[[ "$status" = 204 ]] || error got status "$status" bulk putting batch data
	
	stride=$(( $stride + 1 ))
    done
}

unload()
{
    status=$(mycurl "/subject/${tagdefs[0]}" -X DELETE -o $logfile)
    [[ "$status" = 204 ]] || error got status "$status" bulk deleting batch data
}

if [[ -n "$command" ]]
then
    status=$(mycurl "/session" -d username="$username" -d password="$password" -o $logfile)
    [[ "$status" = 201 ]] || error got "$status" during login

    # note this is pretty fragile...
    # runs the command specified on command-line
    "$command"

    status=$(mycurl "/session" -X DELETE)
    [[ "$status" = 204 ]] || warning got "$status" during logout
else
    help
fi



