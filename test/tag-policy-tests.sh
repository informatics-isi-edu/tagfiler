#!/bin/sh

if [[ $# -lt 3 ]]
then
    cat >&2 <<EOF
usage: $0 <user> <password> <non-user role>

Test against a default tagfiler installation on localhost with default
security behavior allowing username and password POST to the /session
API.

This script runs tests of tag policy models by creating tagdefs and
using them to create and retrieve graph content.  The non-user role is
needed to allow content to be created that the user should not be able
to access.  Some content will remain in the graph since this script
cannot remove it when authz works properly.

EOF
fi

API="https://localhost/tagfiler"
username=$1
password=$2
otherrole=$3

testno=${RANDOM}

tempfile=$(mktemp)

cleanup()
{
    rm -f "$tempfile"
}

trap cleanup 0

mycurl()
{
    local url="$1"
    shift
    curl -b cookie -c cookie -k -w "%{http_code}\n" -s "$@" "${API}${url}"
}

error()
{
    mycurl "/tagdef/foo1A" -X DELETE > /dev/null
    mycurl "/tagdef/foo1B" -X DELETE > /dev/null
    mycurl "/tagdef/foo2A" -X DELETE > /dev/null
    mycurl "/tagdef/foo2B" -X DELETE > /dev/null
    mycurl "/subject/typedef=foo1ref" -X DELETE > /dev/null
    mycurl "/subject/typedef=foo2ref" -X DELETE > /dev/null
    mycurl "/tagdef/foo1" -X DELETE > /dev/null
    mycurl "/tagdef/foo2" -X DELETE > /dev/null
    mycurl "/session" -X DELETE > /dev/null
    cat >&2 <<EOF
$0: $@
EOF
    exit 1
}

status=$(mycurl "/session" -d username="$username" -d password="$password" -o /dev/null)
[[ "$status" -eq 201 ]] || error got "$status" during login

status=$(mycurl "/tagdef/foo1?typestr=text&multivalue=false&readpolicy=anonymous&writepolicy=subject" -X PUT -o /dev/null)
[[ "$status" -eq 201 ]] || error got "$status" creating tagdef foo1

status=$(mycurl "/tagdef/foo2?typestr=text&multivalue=false&readpolicy=anonymous&writepolicy=subjectowner" -X PUT -o /dev/null)
[[ "$status" -eq 201 ]] || error got "$status" creating tagdef foo1

status=$(mycurl "/subject/typedef=foo1ref?typedef%20dbtype=text&typedef%20tagref=foo1" -X PUT -o /dev/null)
[[ "$status" = 201 ]] || error got "$status" creating typedef foo1ref

status=$(mycurl "/subject/typedef=foo2ref?typedef%20dbtype=text&typedef%20tagref=foo2" -X PUT -o /dev/null)
[[ "$status" = 201 ]] || error got "$status" creating typedef foo2ref

status=$(mycurl "/tagdef/foo1A?typestr=foo1ref&multivalue=false&readpolicy=anonymous&writepolicy=object" -X PUT -o /dev/null)
[[ "$status" -eq 201 ]] || error got "$status" creating tagdef foo1A

status=$(mycurl "/tagdef/foo1B?typestr=foo2ref&multivalue=false&readpolicy=anonymous&writepolicy=objectowner" -X PUT -o /dev/null)
[[ "$status" -eq 201 ]] || error got "$status" creating tagdef foo2A

status=$(mycurl "/tagdef/foo2A?typestr=foo2ref&multivalue=false&readpolicy=anonymous&writepolicy=object" -X PUT -o /dev/null)
[[ "$status" -eq 201 ]] || error got "$status" creating tagdef foo2A

status=$(mycurl "/tagdef/foo2B?typestr=foo2ref&multivalue=false&readpolicy=anonymous&writepolicy=objectowner" -X PUT -o /dev/null)
[[ "$status" -eq 201 ]] || error got "$status" creating tagdef foo2B

#mycurl "/query/tagdef:regexp:foo(tagdef;tagdef%20readpolicy;tagdef%20writepolicy)" -H "Accept: text/csv"

cat > $tempfile <<EOF
test${testno}-1,${username},{*},{*}
test${testno}-2,${username},{${username}},{${username}}
test${testno}-3,${username},{},{}
test${testno}-4,${otherrole},{*},{*}
test${testno}-5,${otherrole},{${username}},{${username}}
test${testno}-6,${otherrole},{*},{}
test${testno}-7,${otherrole},{${otherrole}},{${otherrole}}
EOF

NUMVIS=6

status=$(mycurl "/subject/name(name;owner;read%20users;write%20users)" -H "Content-Type: text/csv" -T ${tempfile} -o /dev/null)
[[ "$status" -eq 204 ]] || error got "$status" bulk putting named test subjects "test${testno}-{1..5}"

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
	echo "test${testno}-${s},value$s" > $tempfile
	
	status=$(mycurl "/tags/name(${tag})" -H "Content-Type: text/csv" -T $tempfile -o /dev/null)
	[[ "$status" -eq $code ]] || error got "$status" instead of $code while bulk putting tag $tag on subjects $@

	status=$(mycurl "/tags/name=test${testno}-${s}(${tag}=value${s}prime)" -X PUT -o /dev/null)
	[[ "$status" -eq $code ]] || error got "$status" instead of $code while bulk putting tag $tag on subjects $@

    done > $tempfile

}

tagtest 204 foo1 1 2 3 4 5
tagtest 403 foo1 6

tagtest 204 foo2 1 2 3
tagtest 403 foo2 4 5 6

cat > $tempfile <<EOF
test${testno}-1B,${username},{*},{*},1B,1B
test${testno}-2B,${username},{${username}},{${username}},2B,2B
test${testno}-3B,${username},{},{},3B,3B
test${testno}-4B,${otherrole},{*},{*},4B,4B
test${testno}-5B,${otherrole},{${username}},{${username}},5B,5B
test${testno}-6B,${otherrole},{*},{},6B,6B
test${testno}-7B,${otherrole},{${otherrole}},{${otherrole}},7B,7B
EOF

status=$(mycurl "/subject/name(name;owner;read%20users;write%20users;foo1;foo2)" -H "Content-Type: text/csv" -T ${tempfile} -o /dev/null)
[[ "$status" -eq 204 ]] || error got "$status" bulk putting named test subjects "test${testno}-{1..5}"

lines=$(mycurl "/query/name:regexp:test${testno}-.B(name;owner;read%20users;write%20users)" -H "Accept: text/csv" | wc -l)
[[ "$lines" -eq $(( $NUMVIS + 1 )) ]] || error got $(( $lines - 1 )) results querying when $NUMVIS should be visible

tagreftest()
{
    local code=$1
    local tag=$2
    local val=$3
    shift 3

    for s in $@
    do
	echo "test${testno}-${s},$val" > $tempfile

	status=$(mycurl "/tags/name(${tag})" -H "Content-Type: text/csv" -T $tempfile -o /dev/null)
	[[ "$status" -eq $code ]] || error got "$status" instead of $code while bulk putting tag $tag on subjects $@

	status=$(mycurl "/tags/name=test${testno}-${s}(${tag}=${val})" -X PUT -o /dev/null)
	[[ "$status" -eq $code ]] || error got "$status" instead of $code while bulk putting tag $tag on subjects $@

    done > $tempfile

}

tagreftest 204 foo1A 1B 1 2 3 4 5 6
tagreftest 204 foo1A 2B 1 2 3 4 5 6
tagreftest 204 foo1A 3B 1 2 3 4 5 6
tagreftest 204 foo1A 4B 1 2 3 4 5 6
tagreftest 204 foo1A 5B 1 2 3 4 5 6
tagreftest 403 foo1A 6B 1 2 3 4 5 6

tagreftest 204 foo1B 1B 1 2 3 4 5 6
tagreftest 204 foo1B 2B 1 2 3 4 5 6
tagreftest 204 foo1B 3B 1 2 3 4 5 6
tagreftest 403 foo1B 4B 1 2 3 4 5 6
tagreftest 403 foo1B 5B 1 2 3 4 5 6
tagreftest 403 foo1B 6B 1 2 3 4 5 6

tagreftest 204 foo2A 1B 1 2 3 4 5 6
tagreftest 204 foo2A 2B 1 2 3 4 5 6
tagreftest 204 foo2A 3B 1 2 3 4 5 6
tagreftest 204 foo2A 4B 1 2 3 4 5 6
tagreftest 204 foo2A 5B 1 2 3 4 5 6
tagreftest 403 foo2A 6B 1 2 3 4 5 6

tagreftest 204 foo2B 1B 1 2 3 4 5 6
tagreftest 204 foo2B 2B 1 2 3 4 5 6
tagreftest 204 foo2B 3B 1 2 3 4 5 6
tagreftest 403 foo2B 4B 1 2 3 4 5 6
tagreftest 403 foo2B 5B 1 2 3 4 5 6
tagreftest 403 foo2B 6B 1 2 3 4 5 6

status=$(mycurl "/tagdef/foo1A" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting tagdef foo1A

status=$(mycurl "/tagdef/foo1B" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting tagdef foo1B

status=$(mycurl "/tagdef/foo2A" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting tagdef foo2A

status=$(mycurl "/tagdef/foo2B" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting tagdef foo2B

status=$(mycurl "/subject/typedef=foo1ref" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting typedef foo1ref

status=$(mycurl "/subject/typedef=foo2ref" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting typedef foo2ref

status=$(mycurl "/tagdef/foo1" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting tagdef foo1

status=$(mycurl "/tagdef/foo2" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" deleting tagdef foo2

status=$(mycurl "/session" -X DELETE -o /dev/null)
[[ "$status" = 204 ]] || error got "$status" during logout

exit 0

