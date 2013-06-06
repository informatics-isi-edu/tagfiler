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

SVCPREFIX=${1:-tagfiler}

SVCUSER=${SVCPREFIX}

svn_url=${2:-$(svn info | grep URL: | sed -e 's/URL: //')'@'$(svn info | grep Revision: | sed -e 's/Revision: //')}

settag()
{
    # spredtag spredval tagname value
    local spredtag spredval tagname dbvalue
    local subject old txid
    spredtag="$1"
    spredval="$2"
    tagname="$3"
    dbvalue="$4"

    subject=$(runuser -c "psql -A -t -q" - ${SVCUSER} 2>/dev/null <<EOF
SELECT subject FROM "_${spredtag}" WHERE value = '$spredval';
EOF
)
    if [[ -n "$subject" ]]
    then
	old=$(runuser -c "psql -A -t -q" - ${SVCUSER} 2>/dev/null <<EOF
SELECT subject FROM "_${tagname}" WHERE subject = ${subject};
EOF
)
	if [[ -n "$old" ]]
	then
	    runuser -c "psql -A -t -q" - ${SVCUSER} 2>/dev/null <<EOF
UPDATE "_${tagname}" SET value = $dbvalue WHERE subject = ${subject};
EOF
	else
	    runuser -c "psql -A -t -q" - ${SVCUSER} 2>/dev/null <<EOF
INSERT INTO "_${tagname}" (subject, value) VALUES (${subject}, $dbvalue);
INSERT INTO "subjecttags" (subject, tagname) VALUES (${subject}, '${tagname}');
EOF
	fi
	
	case "$tagname" in
	    subject?last?tagged*|tag?last?modified*)
		# don't recurse here
		:
		;;
	    *)
		settag "$spredtag" "$spredval" "subject last tagged txid" "txid_current()"
		settag "$predtag" "$spredval" "subject last tagged" "'now'"
		settag "tagdef" "${tagname}" "tag last modified txid" "txid_current()"
		settag "tagdef" "${tagname}" "tag last modified" "'now'"
		;;
	esac
    fi
}

settag "config" "tagfiler" "_cfg_system software" "'${svn_url}'"

