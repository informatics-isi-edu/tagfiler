#!/bin/bash

# 
# Copyright 2010 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

#args:

HOME_HOST="$1"
SVCPREFIX="$2"
DBNAME="$3"
admin="$4"

echo args: "$@"

shift 4

# this script will recreate all tables, but only on a clean database

# start a coprocess so we can coroutine with a single transaction
coproc { psql -q -t -A ${DBNAME} ; } 

echo "create catalog tables..."

json_native_func()
{
    cat <<EOF
CREATE FUNCTION val2json($1) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' ELSE CAST(\$1 AS text) END ;
\$\$ LANGUAGE SQL;
EOF
}

json_munge_func()
{
    cat <<EOF
CREATE FUNCTION val2json($1) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' ELSE val2json( CAST(\$1 AS text) ) END ;
\$\$ LANGUAGE SQL;
EOF
}

get_index_name()
{
    # uses coroutined psql directly!

    # get_index_name tablename indexspec
    # e.g. get_index_name '_tagdef' 'subject, value'

    cat >&${COPROC[1]} <<EOF
SELECT count(*) FROM pg_catalog.pg_indexes
WHERE tablename = '$1'
  AND indexdef ~ '[(]$2( text_pattern_ops)?[)]' ;
EOF
    read -u ${COPROC[0]} count

    if [[ $count -ge 1 ]]
    then
	cat >&${COPROC[1]} <<EOF
SELECT indexname FROM pg_catalog.pg_indexes
WHERE tablename = '$1'
  AND indexdef ~ '[(]$2( text_pattern_ops)?[)]'
LIMIT 1 ;
EOF
	read -u ${COPROC[0]} indexname
	printf "%s\n" "$indexname"
    fi
}

cat >&${COPROC[1]} <<EOF
\\set ON_ERROR_STOP

BEGIN;

CREATE FUNCTION val2json(text) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' ELSE '"' || regexp_replace(regexp_replace(\$1, '"', E'\\\\"', 'g'), E'\\n', E'\\\\n', 'g') || '"' END ;
\$\$ LANGUAGE SQL;

CREATE FUNCTION val2json(boolean) RETURNS text AS \$\$
  SELECT CASE WHEN \$1 IS NULL THEN 'null' WHEN \$1 THEN 'true' ELSE 'false' END ;
\$\$ LANGUAGE SQL;

$(json_native_func int)
$(json_native_func bigint)
$(json_native_func float8)
$(json_munge_func date)
$(json_munge_func timestamptz)

CREATE FUNCTION val2json(anyarray) RETURNS text AS \$\$
  SELECT 
    CASE WHEN \$1 IS NULL 
      THEN 'null' 
    ELSE '[' || array_to_string( (SELECT array_agg(val2json(v)) FROM (SELECT unnest(\$1) AS v) s), ',' ) || ']' 
    END ;
\$\$ LANGUAGE SQL;

CREATE FUNCTION jsonfield(text, text) RETURNS text AS \$\$
  SELECT val2json(\$1) || ':' || \$2 ;
\$\$ LANGUAGE SQL;

CREATE FUNCTION jsonobj(text[]) RETURNS text AS \$\$
  SELECT '{' || array_to_string(\$1, ',') || '}' ;
\$\$ LANGUAGE SQL;

CREATE TABLE resources ( subject bigserial PRIMARY KEY );

CREATE FUNCTION tsv_accum(tsvector, tsvector) RETURNS tsvector AS \$\$
  SELECT CASE WHEN \$1 IS NOT NULL THEN \$1 || \$2 ELSE \$2 END ;
\$\$ LANGUAGE SQL;

CREATE AGGREGATE tsv_agg(tsvector) (
  sfunc = tsv_accum,
  stype = tsvector,
  initcond = ''
);

EOF

resources_index=$(get_index_name 'resources' 'subject')

cat >&${COPROC[1]} <<EOF
CLUSTER resources USING "${resources_index}" ;
EOF


# pre-established stored data
# MUST NOT be called more than once with same name during deploy 
db_resources=( 0 )
last_subject=0
dataset_core()
{
    last_subject=$(( ${last_subject} + 1 ))
    cat >&${COPROC[1]} <<EOF
INSERT INTO resources (subject) VALUES (${last_subject});
EOF
}

dataset_complete()
{
   # args: <subjectid> <name> url <url> <owner> [<readuser>]...
   # args: <subjectid> <name> blank <owner> [<readuser>]...
   # args: <subjectid> <name> tagdef <owner> [<readuser>]...
   # args: <subjectid> <name> view <owner> [<readuser>]...

   local subject="$1"
   local file="$2"
   local type="$3"
   local url
   local onclick
   local owner

   shift 3

   case "$type" in
      url|file)
         url="$1"
         shift         

         case "$url" in
            http*:*|/*)
               url="$url"
               ;;
            *)
               url="https://${HOME_HOST}/${SVCPREFIX}/query/$url"
              ;;
         esac
         ;;
      blank|dbtype|tagdef|view)
         :
         ;;
      onclick)
         onclick="$1"
         shift   
         ;;
      *)
         echo "Unsupported dataset format: $*" >&2
         exit 1
         ;;
   esac

   local owner="$1"
   shift

   if [[ -n "$owner" ]]
   then
       tag "$subject" owner text "$owner" >&2
   fi

   while [[ $# -gt 0 ]]
   do
      tag "$subject" "read users" text "$1" >&2
      shift
   done

   case "$type" in
      url|file|onclick)
	 tag "$subject" name text "$file" >&2

	 case "$type" in
	     url)
		 tag "$subject" url text "$url" >&2
		 ;;
	     onclick)
		 tag "$subject" onclick text "$onclick" >&2
		 ;;
	 esac
	 ;;
      view)
	 tag "$subject" "$type" text "$file" >&2
	 ;;
   esac

   insert_or_update $subject "subject last tagged" "'now'"
   insert_or_update $subject "subject last tagged txid" "txid_current()"
}

dataset()
{
    dataset_core
    local subject=${last_subject}
    dataset_complete "$subject" "$@"
}

insert_or_update()
{
    # args: subject tagname 'value' (caller quotes value as necessary)
    cat >&${COPROC[1]} <<EOF
SELECT count(*) FROM "_$2" WHERE subject = $1;
EOF
    read -u ${COPROC[0]} count

    if [[ $count -eq 0 ]]
    then
	cat >&${COPROC[1]} <<EOF
INSERT INTO "_$2" (subject, value) VALUES ($1, $3);
EOF
    else
	cat >&${COPROC[1]} <<EOF
UPDATE "_$2" SET value = $3 WHERE subject = $1;
EOF
    fi

}

tag()
{
   # args: file tag dbtype [value]...
   # for non-empty dbtype
   #     does one default value insert for 0 values
   #     does N value inserts for N>0 values

   local file="$1"
   local tagname="$2"
   local dbtype="$3"
   local count
   shift 3

   echo "set /tags/$file/$tagname=" "$@"
   if [[ -z "$dbtype" ]] || [[ $# -eq 0 ]]
   then
       cat >&${COPROC[1]}  <<EOF
SELECT count(*) FROM "_$tagname" WHERE subject = '$file';
EOF
       read -u ${COPROC[0]} count

       if [[ $count -eq 0 ]]
       then
	   cat >&${COPROC[1]} <<EOF
INSERT INTO "_$tagname" ( subject ) VALUES ( '$file' );
EOF
       fi
   elif [[ $# -gt 0 ]]
   then
       while [[ $# -gt 0 ]]
	 do
	 cat >&${COPROC[1]} <<EOF
SELECT count(*) FROM "_$tagname" WHERE subject = '$file' AND value = '$1';
EOF
	 read -u ${COPROC[0]} count

	 if [[ $count -eq 0 ]]
	 then
	     cat >&${COPROC[1]} <<EOF
INSERT INTO "_$tagname" ( subject, value ) VALUES ( '$file', '$1' );
EOF
	 fi
         shift
      done
   fi

}

tagacl()
{
   # args: tagname {read|write} [value]...
   local tag
   cat >&${COPROC[1]} <<EOF
SELECT subject FROM "_tagdef" WHERE value = '$1';
EOF
   read -u ${COPROC[0]} tag
   local mode=$2
   shift 2
   while [[ $# -gt 0 ]]
   do
      tag "$tag" "tag $mode users" rolepat "$1"
      shift
   done
}

tagdef_phase2()
{
   # args: subject tagname dbtype owner readpolicy writepolicy multivalue [primarykey [tagref]]

   echo "populate tagdef '$2'..." >&2

   dataset_complete "$1" "" tagdef "$4" "*"
   local subject="$1"

   tag "$subject" "tagdef" text "$2" >&2
   tag "$subject" "tagdef active" boolean true >&2

   tag "$subject" "tagdef readpolicy" tagpolicy "$5" >&2
   tag "$subject" "tagdef writepolicy" tagpolicy "$6" >&2

   if [[ "$7" == "true" ]]
   then
      tag "$subject" "tagdef multivalue" boolean true >&2
   else
      tag "$subject" "tagdef multivalue" boolean false >&2
   fi

   tag "$subject" "tagdef dbtype" text "$3" >&2

   if [[ "$8" == "true" ]]
   then
      tag "$subject" "tagdef unique" boolean true >&2
   else
      tag "$subject" "tagdef unique" boolean false >&2
   fi

   if [[ -n "$9" ]]
   then
      tag "$subject" "tagdef tagref" tagdef "$9" >&2
   fi

   insert_or_update $subject "tag last modified" "'now'"
   insert_or_update $subject "tag last modified txid" "txid_current()"
}

tagdef_phase1()
{
   # args: tagname dbtype owner readpolicy writepolicy multivalue [primarykey [tagref]]

   local tagref
   local fk
   local default
   local uniqueval
   local tsvector

   if [[ -n "$2" ]]
   then
      opclass=''
      tsvector=''
      if [[ "$2" = "text" ]]
      then
         default="DEFAULT ''"
	 opclass="text_pattern_ops"
	 tsvector="tsv tsvector,"
      elif [[ "$2" = "boolean" ]]
      then
	 default="DEFAULT False"
      else
         default=""
      fi

      if [[ "$7" = true ]]
      then
         fk="UNIQUE"
      else
         fk=""
      fi

      tagref="$8"

      if [[ -n "$tagref" ]]
      then
	  if [[ "$tagref" != 'id' ]]
	  then
	      fk="${fk} REFERENCES \"_${tagref}\" (value) ON DELETE CASCADE"
	  else
	      fk="${fk} REFERENCES resources (subject) ON DELETE CASCADE"
	  fi
      fi

      if [[ "$6" = "true" ]]
      then
         uniqueval='UNIQUE(subject, value)'
      else
         uniqueval='UNIQUE(subject)'
      fi

      # hack to use implicit indexes created by postgresql rather than creating redundant indexes
      # UNIQUE(subject, value) implies index _$1_subject_key on (subject, value)
      # UNIQUE(subject) implies index _$1_subject_key on (subject)

      if [[ "$2" = "text" ]]
      then
	  # text gets an extra tsvector column in addition to text value column and a trigger to keep the tsvector updated
	  cat >&${COPROC[1]} <<EOF
CREATE TABLE "_$1" ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE, 
                       value text ${default} NOT NULL ${fk}, tsv tsvector, ${uniqueval} );
CREATE INDEX "_$1_value_idx" ON "_$1" (value ${opclass}) ;

CREATE TRIGGER tsvupdate BEFORE INSERT OR UPDATE ON "_$1"
FOR EACH ROW EXECUTE PROCEDURE tsvector_update_trigger(tsv, 'pg_catalog.english', value);

CREATE INDEX "_$1_tsv_idx" ON "_$1" USING gin(tsv);

EOF
      elif [[ "$2" = "tsvector" ]]
      then
	  # tsvector gets a special tsvector column instead of a value column (just for "subject text" system tag)
	  cat >&${COPROC[1]} <<EOF
CREATE TABLE "_$1" ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE, 
                       tsv tsvector, ${uniqueval} );

CREATE INDEX "_$1_tsv_idx" ON "_$1" USING gin(tsv);

EOF
      else
	  # other types just get a normal typed value column
	  cat >&${COPROC[1]} <<EOF
CREATE TABLE "_$1" ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE, 
                       value $2 ${default} NOT NULL ${fk}, ${tsvector}${uniqueval} );
CREATE INDEX "_$1_value_idx" ON "_$1" (value ${opclass}) ;

EOF
      fi

      if [[ "$6" = "true" ]]
      then
	  indexspec="subject, value"
      else
	  indexspec="subject"
      fi
   else
      cat >&${COPROC[1]} <<EOF
CREATE TABLE "_$1" ( subject bigint UNIQUE NOT NULL REFERENCES resources (subject) ON DELETE CASCADE );
EOF
      indexspec="subject"
   fi

   tagdef_cluster_index=$(get_index_name "_$1" "$indexspec")

   cat >&${COPROC[1]} <<EOF
CLUSTER "_$1" USING "${tagdef_cluster_index}" ;
EOF

   dataset_core "" tagdef "$3" "*"
}

tag_subjects=()
tag_names=()
tag_dbtypes=()
tag_owners=()
tag_readpolicies=()
tag_writepolicies=()
tag_multivalues=()

tagdef()
{
   tag_names[${#tag_names[*]}]="$1"
   tag_dbtypes[${#tag_dbtypes[*]}]="$2"
   tag_owners[${#tag_owners[*]}]="$3"
   tag_readpolicies[${#tag_readpolicies[*]}]="$4"
   tag_writepolicies[${#tag_writepolicies[*]}]="$5"
   tag_multivalues[${#tag_multivalues[*]}]="$6"
   tag_uniques[${#tag_uniques[*]}]="$7"
   tag_tagrefs[${#tag_tagrefs[*]}]="$8"
   tagdef_phase1 "$@"
   tag_subjects[${#tag_subjects[*]}]=${last_subject}
}

tagdefs_complete()
{
   local i
   echo ${!tag_names[*]}
   for i in ${!tag_names[*]}
   do
      tagdef_phase2 "${tag_subjects[$i]}" "${tag_names[$i]}" "${tag_dbtypes[$i]}" "${tag_owners[$i]}" "${tag_readpolicies[$i]}" "${tag_writepolicies[$i]}" "${tag_multivalues[$i]}" "${tag_uniques[$i]}" "${tag_tagrefs[$i]}"
   done
}

# sequencing is crucial here to avoid unresolved dependencies!

#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   PKEY     TAGREF
tagdef 'tagdef'              text        ""         anonymous   system       false      true  
tagdef 'tagdef tagref'       text        ""         anonymous   system       false      false    tagdef
tagdef 'tagdef tagref soft'  boolean     ""         anonymous   system       false
tagdef 'tagdef dbtype'       text        ""         anonymous   system       false      false
tagdef 'tagdef unique'       boolean     ""         anonymous   system       false
tagdef 'tagdef multivalue'   boolean     ""         anonymous   system       false
tagdef 'tagdef active'       boolean     ""         anonymous   system       false
tagdef 'tagdef readpolicy'   text        ""         anonymous   system       false
tagdef 'tagdef writepolicy'  text        ""         anonymous   system       false
tagdef 'id'                  int8        ""         anonymous   system       false      true
tagdef 'readok'              boolean     ""         anonymous   system       false
tagdef 'writeok'             boolean     ""         anonymous   system       false
tagdef 'tags present'        text        ""         anonymous   system       true       false     tagdef
tagdef 'view'                text        ""         anonymous   subject      false      true
tagdef 'tag read users'      text        ""         anonymous   subjectowner true
tagdef 'tag write users'     text        ""         anonymous   subjectowner true
tagdef owner                 text        ""         anonymous   tagorowner   false
tagdef created               timestamptz ""         anonymous   system       false
tagdef "read users"          text        ""         anonymous   subjectowner true
tagdef "write users"         text        ""         anonymous   subjectowner true
tagdef "modified by"         text        ""         anonymous   system       false
tagdef modified              timestamptz ""         anonymous   system       false
tagdef "subject last tagged" timestamptz ""         anonymous   system       false
tagdef "subject text"        tsvector    ""         subject     system       false
tagdef "tag last modified"   timestamptz ""         anonymous   system       false
tagdef "subject last tagged txid" int8   ""         anonymous   system       false
tagdef "tag last modified txid" int8     ""         anonymous   system       false
tagdef bytes                 int8        ""         anonymous   system       false
tagdef name                  text        ""         anonymous   subjectowner false      true
tagdef file                  text        ""         system      system       false      true
tagdef content-type          text        ""         anonymous   subject      false
tagdef sha256sum             text        ""         anonymous   subject      false
tagdef "incomplete"          ""          ""         anonymous   subject      false
#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   PKEY     TAGREF

# add special column for tracking subject text tsv freshness
cat >&${COPROC[1]} <<EOF
ALTER TABLE "_subject last tagged txid" ADD COLUMN tsv_txid int8 ;

CREATE INDEX "_subject last tagged txid_tsv_idx" ON "_subject last tagged txid" ( 
  (value > coalesce(tsv_txid, 0))
) WHERE value > coalesce(tsv_txid, 0);

EOF

# complete split-phase definitions and redefine as combined phase
tagdefs_complete
tagdef()
{
    tagdef_phase1 "$@"
    local subject=${last_subject}
    tagdef_phase2 "$subject" "$@"
    tag_names[${#tag_names[*]}]="$1"
}

#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   PKEY     TAGREF
tagdef 'default view'        text        ""         subject     subject      false      false    view
tagdef 'view tags'           text        ""         subject     subject      true       false    tagdef
#      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   PKEY     TAGREF


# drop storage for psuedo tags which we can synthesize from other data
cat >&${COPROC[1]} <<EOF
DROP TABLE "_id";
DROP TABLE "_readok";
DROP TABLE "_writeok";
EOF

tagacl "owner" write "${admin}"


viewdef()
{
    local viewname="$1"
    shift

    dataset "$viewname" view "${admin}" "*"
    local viewsubj
    viewsubj=${last_subject}

    [[ "$#" -gt 0 ]] && tag "$viewsubj" "view tags" tagdef "$@"
}

viewdef default 'id' 'name' bytes owner 'read users' 'write users' "subject last tagged"
viewdef tagdef 'tagdef' "tagdef dbtype" "tagdef tagref" "tagdef tagref soft" "tagdef multivalue" "tagdef unique" "tagdef readpolicy" "tagdef writepolicy" "tag read users" "tag write users" "read users" "write users" "owner"
viewdef view 'view' "view tags" "read users" "write users" "owner"

# remapping rules:
#  srcrole ; dstrole ; reader, ... ; writer, ...
# semi-colons required but readers and writers optional, e.g. srcrole;dstrole;;

# these are actual (not logical) role names just like other ACLs and metadata
# only the python code itself uses logical roles for built-in policies


cat >&${COPROC[1]} <<EOF
INSERT INTO "_tags present" (subject, value)
  SELECT 0, '' WHERE False
  $(for tagname in "${tag_names[@]}"
    do
        if [[ "$tagname" != 'id' ]] && [[ "$tagname" != 'readok' ]] && [[ "$tagname" != 'writeok' ]] && [[ "$tagname" != 'tags present' ]]
        then
           cat <<EOF2
  UNION SELECT DISTINCT subject, '${tagname}' FROM "_${tagname}"
  UNION SELECT subject, 'id' FROM resources
  UNION SELECT subject, 'readok' FROM resources
  UNION SELECT subject, 'writeok' FROM resources
  UNION SELECT subject, 'tags present' FROM resources
EOF2
        fi
    done)
;

SELECT setval('resources_subject_seq', $(( ${last_subject} + 1 )));

COMMIT ;

\q

EOF

: {COPROC[1]}>&-
wait ${COPROC_PID}

