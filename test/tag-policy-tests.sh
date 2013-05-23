#!/bin/sh

if [[ $# -lt 4 ]]
then
    cat >&2 <<EOF
usage: $0 <user> <password> <non-user role> <mutable role>

Test against a default tagfiler installation on localhost with default
security behavior allowing username and password POST to the /session
API using <user> and <password>.

The <non-user role> is used to set ownership of subjects to something
other than the user or its inherited roles, to test non-ownership
conditions.

The <mutable role> is used to temporarily drop ownership of tagdefs in
order to test non-ownership conditions for tagdefs, but then to
reacquire ownership by granting this mutable role to the user so the
test tagdefs can be purged.  For this feature to work, the
tagfiler-config.json must also grant the user rights via the webauthn2
manageusers and manageroles permissions.

This script runs tests of tag policy models by creating tagdefs and
using them to create and retrieve graph content.  The non-user role is
needed to allow content to be created that the user should not be able
to access.  Some content will remain in the graph since this script
cannot remove it when authz works properly.

EOF
    exit 1
fi

API="https://localhost/tagfiler"
username=$1
password=$2
otherrole=$3
mutablerole=$4

testno=${RANDOM}

tempfile=$(mktemp)
tempfile2=$(mktemp)
cookie=$(mktemp)

logfile=$(mktemp)

ACCEPT="${ACCEPT:-text/csv}"

cleanup()
{
    rm -f "$tempfile" "$logfile" "$tempfile2" "$cookie"
}

trap cleanup 0

mycurl()
{
    local url="$1"
    shift
    truncate -s 0 $logfile
    curl -b $cookie -c $cookie -k -w "%{http_code}\n" -s "$@" "${API}${url}"
}

tagdef_writepolicies=(
    subject
    subjectowner
    tag
    tagorsubject
    tagandsubject
    tagorowner
    tagandowner
)

tagdefref_writepolicies=(
    object
    objectowner
    subjectandobject
    tagorsubjectandobject
    tagandsubjectandobject
)

reset()
{
    # blindly tear down everything we setup in this test
    if [[ -n "$mutablerole" ]]
    then
	mycurl "/user/${username}/attribute/${mutablerole}" -X PUT > /dev/null
	mycurl "/session" -X DELETE > /dev/null
	mycurl "/session" -d username="$username" -d password="$password" > /dev/null
    fi

    mycurl "/tagdef/fooread0softref" -X DELETE > /dev/null
    for i in ${!tagdef_writepolicies[@]}
    do
	for j in ${!tagdefref_writepolicies[@]}
	do
	    mycurl "/tagdef/fooread${i}_${j}" -X DELETE > /dev/null
	    mycurl "/tagdef/foo${i}_${j}" -X DELETE > /dev/null
	done
	mycurl "/tagdef/fooread${i}" -X DELETE > /dev/null
	mycurl "/tagdef/foo${i}" -X DELETE > /dev/null
    done

    mycurl "/session" -X DELETE > /dev/null
}

error()
{
    reset
    cat >&2 <<EOF
$0: $@
$(cat $logfile)
EOF
    exit 1
}

status=$(mycurl "/session" -d username="$username" -d password="$password" -o $logfile)
[[ "$status" = 201 ]] || error got "$status" during login

#mycurl "/subject/tagdef:regexp:foo(tagdef;tagdef%20readpolicy;tagdef%20writepolicy)" -H "Accept: ${ACCEPT}"

querytest()
{
    local code=$1
    local count=$2
    local url=$3

    shift 2

    truncate -s 0 $tempfile2
    status=$(mycurl "${url}?limit=none" -H "Accept: ${ACCEPT}" -o $tempfile2)
    [[ "$status" = $code ]] || error got "$status" querying "$url"

    lines=$(grep -v '^[][]*$' < $tempfile2 | wc -l)
    [[ "$lines" -eq $count ]] || error got $lines results querying "$url" when $count should be visible: "$(cat $tempfile2)"
}

# setup the test schema
for i in ${!tagdef_writepolicies[@]}
do
    status=$(mycurl "/tagdef/fooread${i}?dbtype=text&unique=true&multivalue=false&readpolicy=${tagdef_writepolicies[$i]}&writepolicy=subject" -X PUT -o $logfile)
    [[ "$status" = 201 ]] || error got "$status" creating tagdef fooread${i}

    status=$(mycurl "/tagdef/foo${i}?dbtype=text&unique=true&multivalue=false&readpolicy=anonymous&writepolicy=${tagdef_writepolicies[$i]}" -X PUT -o $logfile)
    [[ "$status" = 201 ]] || error got "$status" creating tagdef foo${i}

    for j in ${!tagdefref_writepolicies[@]}
    do
	status=$(mycurl "/tagdef/fooread${i}_${j}?dbtype=text&multivalue=false&readpolicy=${tagdefref_writepolicies[$j]}&writepolicy=subject&tagref=fooread${i}" -X PUT -o $logfile)
	[[ "$status" = 201 ]] || error got "$status" creating tagdef fooread${i}_${j}

	status=$(mycurl "/tagdef/foo${i}_${j}?dbtype=text&multivalue=false&readpolicy=anonymous&writepolicy=${tagdefref_writepolicies[$j]}&tagref=foo${i}" -X PUT -o $logfile)
	[[ "$status" = 201 ]] || error got "$status" creating tagdef foo${i}_${j}
    done
done

# quick test of soft tagref feature...
status=$(mycurl "/tagdef/fooread0softref?dbtype=text&multivalue=false&readpolicy=subject&writepolicy=subject&tagref=fooread0&soft=true" -X PUT -o $logfile)
[[ "$status" = 201 ]] || error got "$status" creating tagdef fooread0softref

status=$(mycurl "/subject/name=softtest${testno}?fooread0softref=softfoo0" -X PUT -o $logfile)
[[ "$status" -eq 201 ]] || error got "$status" putting named soft reference

querytest 200 1 "/subject/fooread0softref=softfoo0(id;name)"
querytest 200 1 "/subject/name=softtest${testno}(id;name)"
querytest 200 0 "/subject/name=softtest${testno}(fooread0softref)/id(id;name)"

status=$(mycurl "/subject/name=softtest${testno}-referant?fooread0=softfoo0" -X PUT -o $logfile)
[[ "$status" -eq 201 ]] || error got "$status" putting named soft referant

querytest 200 1 "/subject/fooread0softref=softfoo0(id;name)"
querytest 200 1 "/subject/name=softtest${testno}(fooread0softref)/id(id;name)"

status=$(mycurl "/subject/name=softtest${testno}-referant" -X DELETE -o $logfile)
[[ "$status" -eq 204 ]] || error got "$status" deleting named soft referant

querytest 200 1 "/subject/fooread0softref=softfoo0(id;name)"
querytest 200 1 "/subject/name=softtest${testno}(id;name)"
querytest 200 0 "/subject/name=softtest${testno}(fooread0softref)/id(id;name)"


# test subjects for later write-authz tests
cat > $tempfile <<EOF
test${testno}-1,${username},{*},{*},,,,,,,
test${testno}-2,${username},{${username}},{${username}},,,,,,,
test${testno}-3,${username},{},{},,,,,,,
test${testno}-4,${otherrole},{*},{*},,,,,,,
test${testno}-5,${otherrole},{${username}},{${username}},,,,,,,
test${testno}-6,${otherrole},{*},{},,,,,,,
test${testno}-7,${otherrole},{${otherrole}},{${otherrole}},,,,,,,
test${testno}-8,${otherrole},{*},{${otherrole}},,,,,,,
test${testno}-1B,${username},{*},{*},1B,1B,1B,1B,1B,1B,1B
test${testno}-2B,${username},{${username}},{${username}},2B,2B,2B,2B,2B,2B,2B
test${testno}-3B,${username},{},{},3B,3B,3B,3B,3B,3B,3B
test${testno}-4B,${otherrole},{*},{*},4B,4B,4B,4B,4B,4B,4B
test${testno}-5B,${otherrole},{${username}},{${username}},5B,5B,5B,5B,5B,5B,5B
test${testno}-6B,${otherrole},{*},{},6B,6B,6B,6B,6B,6B,6B
test${testno}-7B,${otherrole},{${otherrole}},{${otherrole}},7B,7B,7B,7B,7B,7B,7B
test${testno}-8B,${otherrole},{*},{${otherrole}},8B,8B,8B,8B,8B,8B,8B
EOF

status=$(mycurl "/subject/name(name;owner;read%20users;write%20users;foo0;foo1;foo2;foo3;foo4;foo5;foo6)" -H "Content-Type: text/csv" -T ${tempfile} -o $logfile)
[[ "$status" -eq 204 ]] || error got "$status" bulk putting named test subjects 

querytest 200 14 "/subject/name:regexp:test${testno}-(name)"

# start with ownership of all so we can construct all the tag values
# drop ownership of 4..7 before testing read authz
cat > $tempfile <<EOF
test${testno}-1-R,${username},{*},val1,val1,val1,val1,val1,val1,val1
test${testno}-2-R,${username},{${username}},val2,val2,val2,val2,val2,val2,val2
test${testno}-3-R,${username},{},val3,val3,val3,val3,val3,val3,val3
test${testno}-4-R,${username},{*},val4,val4,val4,val4,val4,val4,val4
test${testno}-5-R,${username},{${username}},val5,val5,val5,val5,val5,val5,val5
test${testno}-6-R,${username},{${otherrole}},val6,val6,val6,val6,val6,val6,val6
test${testno}-7-R,${username},{},val7,val7,val7,val7,val7,val7,val7
EOF

status=$(mycurl "/subject/name(name;owner;read%20users;fooread0;fooread1;fooread2;fooread3;fooread4;fooread5;fooread6)" -H "Content-Type: text/csv" -T ${tempfile} -o $logfile)
[[ "$status" -eq 204 ]] || error got "$status" bulk putting named test subjects test${testno}-x-R

querytest 200 7 "/subject/fooread0(name)"

# construct referencing subjects using the above 7 as referenced objects
for o in {1..7}
do

    for j in ${!tagdefref_writepolicies[@]}
    do

	# start with ownership of all so we can construct all the tag values
	# drop ownership of 4..6 before testing read authz
	cat > $tempfile <<EOF
test${testno}-1.${o}.${j}-R,${username},{*},val${o},val${o},val${o},val${o},val${o},val${o},val${o}
test${testno}-2.${o}.${j}-R,${username},{${username}},val${o},val${o},val${o},val${o},val${o},val${o},val${o}
test${testno}-3.${o}.${j}-R,${username},{},val${o},val${o},val${o},val${o},val${o},val${o},val${o}
test${testno}-4.${o}.${j}-R,${username},{*},val${o},val${o},val${o},val${o},val${o},val${o},val${o}
test${testno}-5.${o}.${j}-R,${username},{${username}},val${o},val${o},val${o},val${o},val${o},val${o},val${o}
test${testno}-6.${o}.${j}-R,${username},{},val${o},val${o},val${o},val${o},val${o},val${o},val${o}
EOF

	status=$(mycurl "/subject/name(name;owner;read%20users;fooread0_${j};fooread1_${j};fooread2_${j};fooread3_${j};fooread4_${j};fooread5_${j};fooread6_${j})" -H "Content-Type: text/csv" -T ${tempfile} -o $logfile)
	[[ "$status" -eq 204 ]] || error got "$status" bulk putting named test subjects test${testno}-x.${o}.${j}-R

	querytest 200 6 "/subject/fooread0_${j}=val${o}(name)"

	status=$(mycurl "/tags/name:regexp:test${testno}-%5B456%5D.${o}.${j}-R(owner=${otherrole})" -X PUT -o logfile)
	[[ "$status" = 204 ]] || error got "$status" dropping ownership of named test subjects test${testno}-{4,5,6}.${o}.${j}-R

    done
done

# shed ownership of refenced objects as per above
status=$(mycurl "/tags/name:regexp:test${testno}-%5B4567%5D-R(owner=${otherrole})" -X PUT -o logfile)
[[ "$status" = 204 ]] || error got "$status" dropping ownership of named test subjects test${testno}-{4,5,6}-R

#mycurl "/subject/name:regexp:test${testno}-(name;owner;read%20users;write%20users;readok;writeok)" -H "Accept: ${ACCEPT}"

# begin read-authz tests of pre-defined test data

querytest 200 5 "/subject/fooread0(name)"  # subject readable
querytest 200 3 "/subject/fooread1(name)"  # subjectowner
querytest 200 5 "/subject/fooread2(name)"  # subject readable and tag ACL
querytest 200 5 "/subject/fooread3(name)"  # subject readable and tag ACL
querytest 200 5 "/subject/fooread4(name)"  # subject readable and tag ACL
querytest 200 5 "/subject/fooread5(name)"  # tag ACL
querytest 200 3 "/subject/fooread6(name)"  # subjectowner and tag ACL

for i in 0 2 3 4 5 # objects where referenced tag readpolicy is visible for all subjects
do
    querytest 200 $(( 5 * 5 )) "/subject/fooread${i}_0(name)"
    querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_1(name)" # only three of the 5 objects satisfy objectowner
    querytest 200 $(( 5 * 5 )) "/subject/fooread${i}_2(name)"
    querytest 200 $(( 5 * 5 )) "/subject/fooread${i}_3(name)"
    querytest 200 $(( 5 * 5 )) "/subject/fooread${i}_4(name)"
done

for i in 1 6 # objects where referenced tag readpolicy is visible for owners
do
    querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_0(name)"
    querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_1(name)" 
    querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_2(name)"
    querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_3(name)"
    querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_4(name)"
done

# helper functions for write-authz tests

tagtest_serial()
{
    local code=$1
    local tag=$2
    shift 2

    for s in $@
    do
	local subj="test${testno}-${s}"
	local obj="value$s"
	echo "${subj},${obj}" > $tempfile
	
	status=$(mycurl "/tags/name(${tag})" -H "Content-Type: text/csv" -T $tempfile -o $logfile)
	[[ "$status" = $code ]] || error "/tags/name=$subj(${tag}=$obj)" got "$status" instead of $code while bulk putting tag

    done > $tempfile
}

tagtest()
{
    if [[ $1 != 204 ]]
    then
	tagtest_serial "$@"
	return
    fi

    local code=$1
    local tag=$2
    shift 2

    for s in $@
    do
	local subj="test${testno}-${s}"
	local obj="value$s"
	echo "${subj},${obj}"
	
    done > $tempfile

    status=$(mycurl "/tags/name(${tag})" -H "Content-Type: text/csv" -T $tempfile -o $logfile)
    [[ "$status" = $code ]] || tagtest_serial "$code" "$tag" "$@"
}

tagdeltest_serial()
{
    local code=$1
    local tag=$2
    local prefix=$3
    shift 3

    for s in $@
    do
	local subj="test${testno}-${s}"
	local obj="${prefix}$s"
	
	status=$(mycurl "/tags/name=${subj}(${tag}=${obj})" -X DELETE -o $logfile)
	[[ "$status" = $code ]] || error DELETE "/tags/name=$subj(${tag}=$obj)" got "$status" instead of $code
    done
}

tagdeltest()
{
    if [[ $1 != 204 ]]
    then
	tagdeltest_serial "$@"
	return
    fi

    local code=$1
    local tag=$2
    local prefix=$3
    shift 3

    local subjs=''
    local objs=''

    local sep=''

    for s in $@
    do
	local subj="test${testno}-${s}"
	local obj="${prefix}$s"
	
	subjs+="${sep}${subj}"
	objs+="${sep}${obj}"

	sep=","
    done

    status=$(mycurl "/tags/name=${subjs}(${tag}=${objs})" -X DELETE -o $logfile)
    [[ "$status" = $code ]] || tagdeltest_serial "$code" "$tag" "$prefix" "$@"
}

tagreftest_serial()
{
    local code=$1
    local tagref=$2
    shift 2

    local subjects=()
    local objects=()
    while [[ $1 != '--' ]]
    do
	subjects+=( "$1" )
	shift
    done
    shift
    while [[ $# -gt 0 ]]
    do
	objects+=( "$1" )
	shift
    done

    for i in ${!tagdef_writepolicies[@]}
    do
	local tag=foo${i}_${tagref}
	for s in "${subjects[@]}"
	do
	    for o in "${objects[@]}"
	    do
		local subj="test${testno}-${s}"
		echo "${subj},${o}" > $tempfile
		url="/tags/name(${tag})"
		status=$(mycurl "$url" -H "Content-Type: text/csv" -T $tempfile -o $logfile)
		[[ "$status" = $code ]] || error got "$status" instead of $code while bulk putting "$url" "$(cat $tempfile)"

		local url2="/subject/name=${subj};${tag}=${o}(id;name;${tag})"
		local url3="/tags/name=${subj}(${tag}=${o})"

		if [[ "$status" = 204 ]]
		then
		    truncate -s 0 $tempfile2
		    status=$(mycurl "$url2" -H "Accept: ${ACCEPT}" -o $tempfile2)
		    [[ "$status" = 200 ]] || error got "$status" instead of 200 while querying "$url2"
		    count=$(grep "test${testno}-${s}" "$tempfile2" | wc -l)
		    [[ "$count" -eq 1 ]] || {
			cat $tempfile2
			mycurl "/subject/name=${subj}(id;name;${tag})" -H "Accept: ${ACCEPT}"
			error got $count results instead of 1 while querying "$url2"
		    }
		    if [[ $i = 3 ]]
		    then
			:
			# do not delete tagrefs to foo1 so we can test those triples later...
		    else
			status=$(mycurl "$url3" -X DELETE -o $logfile)
			[[ "$status" = 204 ]] || error got "$status" instead of 204 while deleting "$url3"
		    fi
		fi
	    done
	done
    done
}

tagreftest()
{
    if [[ $1 != 204 ]]
    then
	tagreftest_serial "$@"
	return
    fi

    local code=$1
    local tagref=$2
    shift 2

    local subjects=()
    local objects=()
    local subjslist
    while [[ $1 != '--' ]]
    do
	subjects+=( "$1" )
	shift
    done
    shift
    while [[ $# -gt 0 ]]
    do
	objects+=( "$1" )
	shift
    done

    for o in "${objects[@]}"
    do
	url1="/tags/name("
	url2="/subject/name;"
	subjslist=""
	url3=""
	sep=""
	lsep=""

	truncate -s 0 $tempfile

	for sn in "${!subjects[@]}"
	do
	    local subj="test${testno}-${subjects[$sn]}"
	    printf "${subj}" >> $tempfile

	    for i in ${!tagdef_writepolicies[@]}
	    do
		local tag=foo${i}_${tagref}

		if [[ $sn -eq 0 ]]
		then
		    url1+="${sep}${tag}"
		    url2+="${sep}${tag}=${o}"
		    [[ $i -eq 3 ]] || url3+="${sep}${tag}=${o}"
		    sep=";"
		fi

		printf ",${o}" >> $tempfile
	    done

	    subjslist+="${lsep}${subj}"
	    lsep=","
	    printf "\n" >> $tempfile
	done

	url1+=")"
	url2+="(id;name)"
	url3="/tags/name=${subjslist}(${url3})"

	status=$(mycurl "$url1" -H "Content-Type: text/csv" -T $tempfile -o $logfile)
	[[ "$status" = $code ]] && {

	    truncate -s 0 $tempfile2
	    status=$(mycurl "$url2" -H "Accept: ${ACCEPT}" -o $tempfile2)
	    [[ "$status" = 200 ]] || error got "$status" instead of 200 while querying "$url2"
	    
	    count=$(grep -v '^[][]*$' < $tempfile2 | wc -l)
	    [[ "$count" -eq ${#subjects[@]} ]] || {
		mycurl "/subject/name=${subj}(id;name;${tag})" -H "Accept: ${ACCEPT}"
		error got $count results instead of ${#subjects[@]} while querying "$url2"
	    }

	    status=$(mycurl "$url3" -X DELETE -o $logfile)
	    [[ "$status" = 204 ]] || error got "$status" instead of 204 while deleting "$url3"

	    true

	} || tagreftest_serial "$code" "$tagref" "${subjects[@]}" -- "${o}"

    done
}

# begin write-authz tests

# test writepolicy=subject
tagdeltest 403 foo1 ''             6B    8B # subjects where writeok=False

tagdeltest 404 foo0 value 1 2 3 4 5 6 7 8 # where subject and/or tag is not found

tagtest 204 foo0 1 2 3 4 5       # subjects where writeok=True
tagtest 403 foo0           6   8 # subject where writeok=False
tagtest 409 foo0             7   # subject which is not visible

tagdeltest 204 foo0 value 1 2 3 4 5       # triples where writeok=True
tagdeltest 404 foo0 value           6 7 8 # triples not found

# test writepolicy=subjectowner
tagdeltest 403 foo1 ''        4B 5B 6B   8B # subjects where owner=otherrole

tagtest 204 foo1 1 2 3           # subjects where owner=username
tagtest 403 foo1       4 5 6   8 # subjects where owner=otherrole
tagtest 409 foo1             7   # subject which is not visible

# multiple test combinations here to make sure we observe the right tagpolicy
# e.g. the tagpolicy of the referenced tag is irrelevant when authorizing writes
# to referencing tags


# test writepolicy=object
tagreftest 409 0 1 2 3 4 5 6  8 -- 1C 2C 3C 4C 5C          # tagref key constraint fails
tagreftest 204 0 1 2 3 4 5 6  8 -- 1B 2B 3B 4B 5B          # objects where writeok=True
tagreftest 403 0 1 2 3 4 5 6  8 --                6B    8B # object where writeok=False
tagreftest 409 0 1 2 3 4 5 6  8 --                   7B    # object which is not visible


# test writepolicy=objectowner
tagreftest 204 1 1 2 3 4 5 6  8 -- 1B 2B 3B                # objects which we own
tagreftest 403 1 1 2 3 4 5 6  8 --          4B 5B 6B    8B # objects which we do not own
tagreftest 409 1 1 2 3 4 5 6  8 --                   7B    # object which is not visible

# test writepolicy=subjectandobject
tagreftest 204 2 1 2 3 4 5      -- 1B 2B 3B 4B 5B          # subjects where writeok=True and objects where writeok=True
tagreftest 403 2 1 2 3 4 5      --                6B    8B # subjects where writeok=True and objects where writeok=False
tagreftest 403 2           6  8 -- 1B 2B 3B 4B 5B          # subjects where writeok=False and objects where writeok=True
tagreftest 403 2           6  8 --                6B    8B # subject and object where writeok=False

# now test with us in ACLs... (we're in ACL because we own tagdef)
tagtest 204 foo2 1 2 3 4 5 6  8 # writepolicy=tag and tag ACL is True
tagtest 204 foo3 1 2 3 4 5 6  8 # writepolicy=tagorsubject and tag ACL is True
tagtest 204 foo4 1 2 3 4 5      # writepolicy=tagandsubject and tag ACL is True and subject writeok=True
tagtest 403 foo4           6  8 # writepolicy=tagandsubject and subject writeok=False
tagtest 204 foo5 1 2 3 4 5 6 # writepolicy=tagorowner and ACL is True
tagtest 204 foo6 1 2 3       # writepolicy=tagandowner and ACL is True and owner=username
tagtest 403 foo6 4 5 6       # writepolicy=tagandowner and owner=otherrole
tagreftest 204 3 1 2 3 4 5 6 -- 1B 2B    4B 5B 6B 3B # writepolicy=tagorsubjectandobject and ACL is True (3B is last for deletion tests below)
tagreftest 204 4 1 2 3 4 5   -- 1B 2B 3B 4B 5B    # writepolicy=tagandsubjectandobject and ACL is True and subject writeok=True and object writeok=True
tagreftest 403 4           6 -- 1B 2B 3B 4B 5B 6B # writepolicy=tagandsubjectandobject where writeok=False
tagreftest 403 4 1 2 3 4 5   --                6B # writepolicy=tagandsubjectandobject where object writeok=False

status=$(mycurl "/subject/subject%20text:word:${username}(name)" -H "Accept: ${ACCEPT}" -o $logfile)
[[ $status = 200 ]] || error got "$status" during free-text query test
count=$(grep -v '^[][]*$' < $logfile | wc -l)
[[ $count -gt 5 ]] || error found too few results during free-text query test for ${username}

if [[ -n "$mutablerole" ]]
then
    # can only test negative tag ACLs if we can rescind ownership while reacquiring it for cleanup later

    # make sure we're not in mutablerole
    status=$(mycurl "/user/${username}/attribute/${mutablerole}" -X DELETE -o $logfile)
    [[ "$status" = 204 ]] || [[ "$status" = 404 ]] || error got "$status" removing ${username} from ${mutablerole}

    # restart session to ensure fresh attribute set
    status=$(mycurl "/session" -X DELETE -o $logfile)
    [[ "$status" = 204 ]] || error got "$status" during logout
    
    status=$(mycurl "/session" -d username="$username" -d password="$password" -o $logfile)
    [[ "$status" -eq 201 ]] || error got "$status" during login

    # change owner of tagdefs to mutablerole
    status=$(mycurl "/tags/tagdef:regexp:foo;owner=${username}(owner=${mutablerole})" -X PUT -o $logfile)
    [[ "$status" = 204 ]] || error got "$status" setting tagdef foo tagdef owners to ${mutablerole}

    querytest 200 0 "/subject/tagdef:regexp:foo;owner=${username}(tagdef;owner;tagdef%20readpolicy;tag%20read%20users)"

    # do read-tests again w/o tag ACL permissions...
    querytest 200 5 "/subject/fooread0(name)"  # subject readable
    querytest 200 3 "/subject/fooread1(name)"  # subjectowner
    querytest 200 0 "/subject/fooread2(name)"  # no ACL
    querytest 200 5 "/subject/fooread3(name)"  # subject readable
    querytest 200 0 "/subject/fooread4(name)"  # no ACL
    querytest 200 3 "/subject/fooread5(name)"  # owner
    querytest 200 0 "/subject/fooread6(name)"  # no ACL

    for i in 0 3 # objects where referenced tag readpolicy is visible for all objects
    do
	querytest 200 $(( 5 * 5 )) "/subject/fooread${i}_0(name)"
	querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_1(name)" # only three of the 5 objects satisfy objectowner
	querytest 200 $(( 5 * 5 )) "/subject/fooread${i}_2(name)"
	querytest 200 $(( 5 * 5 )) "/subject/fooread${i}_3(name)"
	querytest 200 $(( 5 * 0 )) "/subject/fooread${i}_4(name)" # no ACL
    done
    
    for i in 2 4 6 # objects where referenced tag readpolicy is not visible
    do
	querytest 200 $(( 5 * 0 )) "/subject/fooread${i}_0(name)"
	querytest 200 $(( 5 * 0 )) "/subject/fooread${i}_1(name)"
	querytest 200 $(( 5 * 0 )) "/subject/fooread${i}_2(name)"
	querytest 200 $(( 5 * 0 )) "/subject/fooread${i}_3(name)"
	querytest 200 $(( 5 * 0 )) "/subject/fooread${i}_4(name)"
    done
    
    for i in 1 5 # objects where referenced tag readpolicy is visible for owners
    do
	querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_0(name)"
	querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_1(name)" 
	querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_2(name)"
	querytest 200 $(( 5 * 3 )) "/subject/fooread${i}_3(name)"
	querytest 200 $(( 5 * 0 )) "/subject/fooread${i}_4(name)" # no ACL
    done

    # do write-tests again...
    tagtest 403 foo2 1 2 3 4 5 6 # writepolicy=tag and tag ACL is False
    tagtest 204 foo3 1 2 3 4 5   # writepolicy=tagorsubject and subject writeok=True
    tagtest 403 foo3           6 # writepolicy=tagorsubject and subject writeok=True
    tagtest 403 foo4 1 2 3 4 5 6 # writepolicy=tagandsubject and tag ACL is False
    tagtest 204 foo5 1 2 3       # writepolicy=tagorowner and owner=username
    tagtest 403 foo5 4 5 6       # writepolicy=tagorowner and owner=otherrole and ACL is False
    tagtest 403 foo6 1 2 3 4 5 6 # writepolicy=tagandowner and ACL is False
    tagreftest 204 3 1 2 3 4 5   -- 1B 2B    4B 5B    3B # writepolicy=tagorsubjectandobject and subject writeok=True and object writeok=True (3B is last for deletion tests below)
    tagreftest 403 3           6 -- 1B 2B 3B 4B 5B 6B # writepolicy=tagorsubjectandobject and subject writeok=False
    tagreftest 403 3 1 2 3 4 5   --                6B # writepolicy=tagorsubjectandobject and object writeok=False
    tagreftest 403 4 1 2 3 4 5 6 -- 1B 2B 3B 4B 5B 6B # writepolicy=tagandsubjectandobject and ACL is False

fi

tagdeltest 204 foo0 '' 1B 2B 3B 4B 5B
tagdeltest 403 foo0 ''                6B    8B
tagdeltest 404 foo0 ''                   7B

# test change to referenced tag foo1, for which we already deleted references above
tagtest 204 foo1 1B 2B 3B

# test implicit delete path via change to referenced tag foo3, for which we preserved references above
# this depends on 3B being the final object tested above for tagreftest 204 3 ...
truncate -s 0 $tempfile2
status=$(mycurl "/subject/foo3_3(id;name;foo3_3;subject%20last%20tagged)id?limit=none" -H "Accept: ${ACCEPT}" -o $tempfile2)
[[ "$status" = 200 ]] || error got status $status querying "foo3_3"
count=$(grep -v '^[][]*$' < $tempfile2 | wc -l)
[[ $count -gt 0 ]] || error failed to find existing references foo3_3 to tag foo3

tagtest 204 foo3 1B 2B 3B 4B 5B

truncate -s 0 $tempfile2
status=$(mycurl "/subject/foo3_3(id;name;foo3_3;subject%20last%20tagged)id?limit=none" -H "Accept: ${ACCEPT}" -o $tempfile2)
[[ "$status" = 200 ]] || error got status $status querying "foo3_3"
count=$(grep -v '^[][]*$' < $tempfile2 | wc -l)
[[ $count -eq 0 ]] || error found $count existing references foo3_3 to tag foo3 after they should have disappeared: "$(cat $tempfile2)"


deletetest_serial()
{
    local code=$1
    shift

    for n in $@
    do
	status=$(mycurl "/subject/name=test${testno}-${n}" -X DELETE -o $logfile)
	[[ "$status" = ${code} ]] || error got "$status" instead of "$code" removing "name=test${testno}-${n}"
    done
}

deletetest()
{
    if [[ $1 != 204 ]]
    then
	deletetest_serial "$@"
	return
    fi

    local code=$1
    shift

    url="/subject/name="
    sep=""

    for n in $@
    do
	url+="${sep}test${testno}-${n}"
	sep=","
    done
    status=$(mycurl "$url" -X DELETE -o $logfile)
    [[ "$status" = ${code} ]] || deletetest_serial "$code" "$@"
}

deletetest 403           6   8           # subjects not writeable
deletetest 404             7             # subject not visible
deletetest 204 1 2 3 4 5                 # subjects writeable

deletetest 403                6B    8B  # subjects not writeable
deletetest 404                   7B     # subject not visible
deletetest 204 1B 2B 3B 4B 5B           # subjects writeable

# tear down the test schema
reset
exit 0

