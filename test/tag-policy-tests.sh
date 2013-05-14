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

logfile=$(mktemp)

cleanup()
{
    rm -f "$tempfile" "$logfile" "$tempfile2"
}

trap cleanup 0

mycurl()
{
    local url="$1"
    shift
    truncate -s 0 $logfile
    curl -b cookie -c cookie -k -w "%{http_code}\n" -s "$@" "${API}${url}"
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

    for i in ${!tagdef_writepolicies[@]}
    do
	for j in ${!tagdefref_writepolicies[@]}
	do
	    mycurl "/tagdef/foo${i}_${j}" -X DELETE > /dev/null
	done
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

# setup the test schema
for i in ${!tagdef_writepolicies[@]}
do
    status=$(mycurl "/tagdef/foo${i}?dbtype=text&multivalue=false&readpolicy=anonymous&writepolicy=${tagdef_writepolicies[$i]}" -X PUT -o $logfile)
    [[ "$status" = 201 ]] || error got "$status" creating tagdef foo${i}

    for j in ${!tagdefref_writepolicies[@]}
    do
	status=$(mycurl "/tagdef/foo${i}_${j}?dbtype=text&multivalue=false&readpolicy=anonymous&writepolicy=${tagdefref_writepolicies[$j]}&tagref=foo${i}" -X PUT -o $logfile)
	[[ "$status" = 201 ]] || error got "$status" creating tagdef foo${i}_${j}
    done

done

#mycurl "/query/tagdef:regexp:foo(tagdef;tagdef%20readpolicy;tagdef%20writepolicy)" -H "Accept: text/csv"

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

NUMVIS=14

status=$(mycurl "/subject/name(name;owner;read%20users;write%20users;foo0;foo1;foo2;foo3;foo4;foo5;foo6)" -H "Content-Type: text/csv" -T ${tempfile} -o $logfile)
[[ "$status" -eq 204 ]] || error got "$status" bulk putting named test subjects 

lines=$(mycurl "/query/name:regexp:test${testno}-(name;owner;read%20users;write%20users)" -H "Accept: text/csv" | wc -l)
[[ "$lines" -eq $(( $NUMVIS + 1 )) ]] || error got $(( $lines - 1 )) results querying when $NUMVIS should be visible

#mycurl "/query/name:regexp:test${testno}-(name;owner;read%20users;write%20users;readok;writeok)" -H "Accept: text/csv"

tagtest()
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

tagdeltest()
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

tagreftest()
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

		if [[ "$status" = 204 ]]
		then
		    local url2="/query/name=${subj};${tag}=${o}(name;${tag})"
		    status=$(mycurl "$url2" -H "Accept: text/csv" -o $tempfile2)
		    [[ "$status" = 200 ]] || error got "$status" instead of 200 while querying "$url2"
		    count=$(grep "test${testno}-${s}" "$tempfile" | wc -l)
		    [[ "$count" -eq 1 ]] || {
			cat $tempfile2
			mycurl "/query/name=${subj}(id;name;${tag})" -H "Accept: text/csv"
			error got $count results instead of 1 while querying "/query/name=${subj}(${tag}=${o})"
		    }
		fi
	    done
	done
    done
}

getreftest()
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
		url="/query/name=${subj};${tag}=${o}(name;${tag})"
		status=$(mycurl "$url" -H "Accept: text/csv" -o $tempfile)
		[[ "$status" -eq $code ]] || {
		    error got "$status" instead of $code while getting "$url" 
		    mycurl "/query/name=${subj}(name;${tag})" -H "Accept: application/json" 
		    }
		count=$(wc -l < $tempfile)
		[[ $count -eq 1 ]] || {
		    error got "$count" results while querying "$url" 
		    mycurl "/query/name=${subj}(name;${tag})" -H "Accept: application/json" 
		}
	    done
	done
    done
}

refdeltest()
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
		local url="/tags/name=${subj}(${tag}=${o})"
		status=$(mycurl "$url" -X DELETE -o $logfile)
		[[ "$status" -eq $code ]] || error DELETE "$url" got "$status" instead of $code
	    done
	done
    done
}

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
tagreftest 204 0 1 2 3 4 5 6  8 -- 1B 2B 3B 4B 5B          # objects where writeok=True
getreftest 200 0 1 2 3 4 5 6  8 -- 1B 2B 3B 4B 5B 
refdeltest 204 0 1 2 3 4 5 6  8 -- 1B 2B 3B 4B 5B 

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
tagreftest 204 3 1 2 3 4 5 6 -- 1B 2B 3B 4B 5B 6B # writepolicy=tagorsubjectandobject and ACL is True
tagreftest 204 4 1 2 3 4 5   -- 1B 2B 3B 4B 5B    # writepolicy=tagandsubjectandobject and ACL is True and subject writeok=True and object writeok=True
tagreftest 403 4           6 -- 1B 2B 3B 4B 5B 6B # writepolicy=tagandsubjectandobject where writeok=False
tagreftest 403 4 1 2 3 4 5   --                6B # writepolicy=tagandsubjectandobject where object writeok=False


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
    
    # test without us in tag ACLs...
    tagtest 403 foo2 1 2 3 4 5 6 # writepolicy=tag and tag ACL is False
    tagtest 204 foo3 1 2 3 4 5   # writepolicy=tagorsubject and subject writeok=True
    tagtest 403 foo3           6 # writepolicy=tagorsubject and subject writeok=True
    tagtest 403 foo4 1 2 3 4 5 6 # writepolicy=tagandsubject and tag ACL is False
    tagtest 204 foo5 1 2 3       # writepolicy=tagorowner and owner=username
    tagtest 403 foo5 4 5 6       # writepolicy=tagorowner and owner=otherrole and ACL is False
    tagtest 403 foo6 1 2 3 4 5 6 # writepolicy=tagandowner and ACL is False
    tagreftest 204 3 1 2 3 4 5   -- 1B 2B 3B 4B 5B    # writepolicy=tagorsubjectandobject and subject writeok=True and object writeok=True
    tagreftest 403 3           6 -- 1B 2B 3B 4B 5B 6B # writepolicy=tagorsubjectandobject and subject writeok=False
    tagreftest 403 3 1 2 3 4 5   --                6B # writepolicy=tagorsubjectandobject and object writeok=False
    tagreftest 403 4 1 2 3 4 5 6 -- 1B 2B 3B 4B 5B 6B # writepolicy=tagandsubjectandobject and ACL is False

fi

tagdeltest 204 foo0 '' 1B 2B 3B 4B 5B
tagdeltest 403 foo0 ''                6B    8B
tagdeltest 409 foo0 ''                   7B

deletetest()
{
    local code=$1
    shift

    for n in $@
    do
	status=$(mycurl "/subject/name=test${testno}-${n}" -X DELETE -o $logfile)
	[[ "$status" = ${code} ]] || error got "$status" instead of "$code" removing "name=test${testno}-${n}"
    done
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

