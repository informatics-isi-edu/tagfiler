#!/bin/sh

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

DBNAME="$1"

echo args: "$@"

shift 1

# this script will recreate all tables, but only on a clean database

# this is installed to /usr/local/bin
tagfiler-webauthn2-deploy.py

# start a coprocess so we can coroutine with a single transaction
coproc { psql -q -t -A ${DBNAME} ; }

echo "create core tables..."

cat >&${COPROC[1]} <<EOF
\\set ON_ERROR_STOP

BEGIN;

CREATE TABLE catalogs (
	id bigserial PRIMARY KEY,
	owner text NOT NULL,
	admin_users text[] NOT NULL,
	write_users text[] NOT NULL,
	read_users text[] NOT NULL,
        active boolean,
	name text,
	description text,
        config text);

COMMIT;

\q

EOF

: {COPROC[1]}>&-
wait ${COPROC_PID}
