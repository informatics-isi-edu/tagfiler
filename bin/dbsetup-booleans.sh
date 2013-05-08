#!/bin/sh

## run once to upgrade some tagdefs on the fly...
## copy to daemon account and run it there as the daemon user

mypsql()
{
    local input=$(cat)
    if [[ -n "$input" ]]
    then
	echo "mypsql " "$@" -c "\"${input}\"" >&2
	psql "$@" -c  "${input}"
    else
	echo "mypsql " "$@" >&2
	psql "$@"
    fi
}

empty2boolean()
{
    echo converting tag "$1" to boolean type >&2
    mypsql <<EOF
BEGIN ;
ALTER TABLE "_${1}" ADD COLUMN value boolean DEFAULT False ;
UPDATE "_${1}" SET value = True ;
UPDATE "_tagdef type" AS t SET value = 'boolean' FROM "_tagdef" AS d WHERE t.subject = d.subject AND d.value = '${1}' ;
COMMIT
EOF
}

insert_value_from()
{
    echo inserting into "$1" value "$2" for extra rows from "$3" >&2
    mypsql <<EOF
INSERT INTO "_${1}" (subject, value) 
  SELECT subject, $2 
  FROM (SELECT subject FROM "_${3}"
        EXCEPT
        SELECT subject FROM "_${1}") AS t ;
EOF
}

insert_or_update_singleval_tag()
{
    # subject tagname [value]
    local subject="$1"
    local tagname="$2"

    if [[ $# -gt 2 ]]
    then
	setstmt="SET value = $3"
	columns="subject, value"
	values="$subject, $3"
    else
	setstmt="SET subject = $subject"
	columns="subject"
	values="$subject"
    fi

    echo insert_or_update "$tagname" "( $columns )" "= $values " >&2

    count=$(mypsql -A -t -q <<EOF
SELECT count(*) FROM "_$tagname" WHERE subject = $subject ;
EOF
    )
    if [[ $count -eq 0 ]]
    then
	mypsql -q -t -A <<EOF
INSERT INTO "_$tagname" ( ${columns} ) VALUES ( ${values} ) ;
EOF
    else
	mypsql -q -t -A <<EOF
UPDATE "_$tagname" ${setstmt} WHERE subject = $subject ;
EOF
    fi

    mypsql -q -t -A <<EOF
INSERT INTO subjecttags ( subject, tagname ) 
   SELECT $subject, '$tagname'
   EXCEPT
   SELECT subject, tagname FROM subjecttags ;
EOF

    update_tag_meta_tags "$subject" "$tagname"
}

insert_or_update_multival_tag()
{
    # subject tagname value...
    local subject="$1"
    local tagname="$2"
    shift 2

    while [[ $# -gt 0 ]]
    do

      mypsql -q -t -A <<EOF
BEGIN ;
INSERT INTO "_$tagname" ( subject, value ) 
   SELECT $subject, $1 
   EXCEPT
   SELECT subject, value FROM "_$tagname" ;
INSERT INTO subjecttags ( subject, tagname ) 
   SELECT $subject, '$tagname'
   EXCEPT
   SELECT subject, tagname FROM subjecttags ;
COMMIT
EOF

      shift
    done

    update_tag_meta_tags "$subject" "$tagname"
}

update_tag_meta_tags()
{
   # args: subject tagname 

   case "$2" in
       "subject last tagged"|"tag last modified"|"subject last tagged txid"|"tag last modified txid")
	   return
	   ;;
   esac

   local subject="$1"
   local tagname="$2"

   local msubject=$(mypsql -q -A -t <<EOF
SELECT subject FROM "_tagdef" WHERE value = '$tagname'
EOF
   )

   insert_or_update_singleval_tag "$subject" "subject last tagged" "'now'"
   insert_or_update_singleval_tag "$subject" "subject last tagged txid" "txid_current()"

   insert_or_update_singleval_tag "$msubject" "tag last modified" "'now'"
   insert_or_update_singleval_tag "$msubject" "tag last modified txid" "txid_current()"
}

# PERFORM UPGRADE


# create typedef=boolean

subject=$(mypsql -A -t -q <<EOF
INSERT INTO resources DEFAULT VALUES RETURNING subject;
EOF
)

insert_or_update_singleval_tag "$subject" "typedef" "'boolean'"
insert_or_update_singleval_tag "$subject" "typedef dbtype" "'boolean'"
insert_or_update_singleval_tag "$subject" "typedef description" "'Boolean (true or false)'"
insert_or_update_multival_tag "$subject" "typedef values" "'True True'" "'False False'"
insert_or_update_multival_tag "$subject" "read users" "'*'"

# convert built-in tagdefs from empty to boolean 
for tag in "tagdef "{active,multivalue,unique}
do
  empty2boolean "$tag"
  insert_value_from "$tag" "False" "tagdef"
done

for tag in "_cfg_client "{up,down}"load chunks" "_cfg_webauthn require"
do
  empty2boolean "$tag"
done

