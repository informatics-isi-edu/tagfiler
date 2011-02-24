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

# This script generates test cases for all policy combinations
# Redirect the output to a file and then execute that file 

# Set in the following definitions your test values for:
#	<hostname>			- hostname of the service
#	<user>				- authentication user
#	<password>			- authentication password
#	<guest password>	- guest authentication password
#	<AuthType>			- authentication type (digest or basic)
#	<file>				- the path of the file to be uploaded
#	<tagfiler>			- the service prefix

echo "#!/bin/sh"
echo ""

echo HOST=http://<hostname>
echo AUTHENTICATION=<user>:<password>
echo AUTHENTICATION_GUEST=guest:<guest password>
echo AUTHENTICATION_METHOD=<AuthType>
echo FILE=<file>
echo URL=http://www.yahoo.com
echo SVCPREFIX=<tagfiler>
echo ""

echo COMMON_OPTIONS=\"-s -S -k\"
echo LOGFILE=psoc_acl.log
echo TEMPFILE=psocTemp
DATASET1=Spectrophotometry
DATASET2=Retinoblastoma
echo ""

echo "START=\$(date +%s)"
echo ""

echo "date > \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# Tags Actions"
echo ""

echo "# Define the tags with POST"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags"
echo "echo \"List the tags\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"guest\""
echo "echo \"List the tags by user \\\"guest\\\"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tag definitions"
echo ""

echo "echo \"List the tag definitions\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags by user \"guest\""
echo ""

echo "echo \"List the tag definitions by user \\\"guest\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Delete the tags with POST"
echo ""

echo "echo \"Delete \\\"tag_read_anonymous_write_anonymous\\\" tag by user \\\"guest\\\" with POST\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=ConfirmDelete\" \"\$HOST/\$SVCPREFIX/tagdef/tag_read_anonymous_write_anonymous\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "echo \"Delete the tag definitions with POST\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=ConfirmDelete\" \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Define the tags with PUT"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}?typestr=text&multivalue=true&readpolicy=${i}&writepolicy=${j}\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags"
echo "echo \"List the tags\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"guest\""
echo "echo \"List the tags by user \\\"guest\\\"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tag definitions"
echo ""

echo "echo \"List the tag definitions\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags by user \"guest\""
echo ""

echo "echo \"List the tag definitions by user \\\"guest\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Delete the tags with DELETE"
echo ""

echo "echo \"Delete \\\"tag_read_anonymous_write_anonymous\\\" tag by user \\\"guest\\\" with DELETE\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_anonymous_write_anonymous\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "echo \"Delete the tag definitions with DELETE\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Define the tags with POST"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Define the tag readers and writers with POST"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Define read user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-readers=true&val-readers=guest&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define read user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-readers=true&val-readers=guest2&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Define write user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-writers=true&val-writers=guest&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define write user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-writers=true&val-writers=guest2&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"guest\""
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"guest\\\"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Delete the tag readers and writers with POST"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Delete read user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag=readers&value=guest&action=delete\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete read user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag=readers&value=guest2&action=delete\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Delete write user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag=writers&value=guest&action=delete\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete write user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag=writers&value=guest2&action=delete\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"guest\""
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"guest\\\"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Define the tag readers and writers with PUT"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Define read user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/readers=guest\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define read user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/readers=guest2\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Define write user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/writers=guest\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define write user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/writers=guest2\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"guest\""
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"guest\\\"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Delete the tag readers and writers with DELETE"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Delete read user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/readers=guest\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete read user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/readers=guest2\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Delete write user \\\"guest\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/writers=guest\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete write user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}/writers=guest2\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"guest\""
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"guest\\\"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "echo \"Delete the tag definitions with DELETE\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags"
echo "echo \"List the tags\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"guest\""
echo "echo \"List the tags by user \\\"guest\\\"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# Define the tags with POST"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Define \\\"tag_no_content_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag-1=tag_no_content_read_${i}_write_${j}&type-1=&multivalue-1=false&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Define the tag readers and writers with POST"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Define read user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-readers=true&val-readers=guest2&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Define write user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-writers=true&val-writers=guest2&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Adding Dataset Tags"
echo ""

echo "echo \"Define \\\"$DATASET1\\\" dataset with PUT\"  >> \$LOGFILE"
echo "date >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -T \"\$FILE\" \"\$HOST/\$SVCPREFIX/file/$DATASET1\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "date >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "echo \"Add \\\"read users\\\" tag to dataset \\\"$DATASET1\\\" with value \\\"*\\\" using POST\"  >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=put&set-read%20users=true&val-read%20users=*\" \"\$HOST/\$SVCPREFIX/tags/$DATASET1\" >> \$LOGFILE"
echo ""

echo "echo \"Define \\\"$DATASET2\\\" dataset with url POST\"  >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=put&url=\$URL\" \"\$HOST/\$SVCPREFIX/file/$DATASET2\" >> \$LOGFILE"
echo ""

echo "echo \"Add \\\"read users\\\" tag to dataset \\\"$DATASET2\\\" with value \\\"*\\\" using POST\"  >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=put&set-read%20users=true&val-read%20users=*\" \"\$HOST/\$SVCPREFIX/tags/$DATASET2\" >> \$LOGFILE"
echo ""

echo "# Add values to the tags with POST"
echo ""

for k in $DATASET1 $DATASET2
do
	for i in anonymous file fowner tag users
	do
		for j in anonymous file fowner tag users
		do
			echo "echo \"Add \\\"tag_no_content_read_${i}_write_${j}\\\" tag to dataset \\\"${k}\\\" using POST\"  >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=put&set-tag_no_content_read_${i}_write_${j}=true\" \"\$HOST/\$SVCPREFIX/tags/${k}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Add \\\"tag_read_${i}_write_${j}\\\" tag to dataset \\\"${k}\\\" with values \\\"tag_read_${i}_write_${j}_VALUE1\\\" and \\\"tag_read_${i}_write_${j}_VALUE2\\\" using POST\"  >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=put&set-tag_read_${i}_write_${j}=true&val-tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1\" \"\$HOST/\$SVCPREFIX/tags/${k}\" >> \$LOGFILE"
			echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"action=put&set-tag_read_${i}_write_${j}=true&val-tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE2\" \"\$HOST/\$SVCPREFIX/tags/${k}\" >> \$LOGFILE"
			echo ""
			if [ "$i" == "tag" ]
			then
				echo "echo \"Define read user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
				echo "echo \"\" >> \$LOGFILE"
				echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-readers=true&val-readers=guest2&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
				echo ""
			fi
			if [ "$j" == "tag" ]
			then
				echo "echo \"Define write user \\\"guest2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
				echo "echo \"\" >> \$LOGFILE"
				echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -d \"set-writers=true&val-writers=guest2&action=put\" \"\$HOST/\$SVCPREFIX/tagdefacl/tag_read_${i}_write_${j}\" >> \$LOGFILE"
				echo ""
			fi
		done
	done
done

echo "# Get dataset tags"
echo ""

for k in $DATASET1 $DATASET2
do
	echo "echo \"Fetch dataset \\\"${k}\\\" tags\"  >> \$LOGFILE"
	echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/${k}\"  | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
	echo "echo \"\" >> \$LOGFILE"
	echo ""
	echo "echo \"Fetch dataset \\\"${k}\\\" tags by user \\\"guest\\\"\"  >> \$LOGFILE"
	echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/${k}\"  | xsltproc --html dataset.xslt - | grep -v \"<?xml\" | grep -v \"^\$\" >> \$LOGFILE"
	echo "echo \"\" >> \$LOGFILE"
	echo ""
done

echo "# Queries"
echo ""

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Query for \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE1\\\" AND \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE2\\\"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1,tag_read_${i}_write_${j}_VALUE2\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
		echo "echo \"Query for \\\"tag_no_content_read_${i}_write_${j}\\\" EXISTS\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_no_content_read_${i}_write_${j}\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
		echo "echo \"Query for \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE1\\\" AND \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE2\\\" for user \\\"guest\\\"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1,tag_read_${i}_write_${j}_VALUE2\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
		echo "echo \"Query for \\\"tag_no_content_read_${i}_write_${j}\\\" EXISTS for user \\\"guest\\\"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION_GUEST --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_no_content_read_${i}_write_${j}\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
	done
done

for i in anonymous file fowner tag users
do
	for j in anonymous file fowner tag users
	do
		echo "echo \"Delete \\\"tag_no_content_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_no_content_read_${i}_write_${j}\" >> \$LOGFILE"
		echo ""
		echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Delete the datasets"
echo ""

for k in $DATASET1 $DATASET2
do
	echo "echo \"Delete \\\"$DATASET1\\\" dataset with DELETE\"  >> \$LOGFILE"
	echo "echo \"\" >> \$LOGFILE"
	echo "curl -u \$AUTHENTICATION --\$AUTHENTICATION_METHOD \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/file/${k}\" >> \$LOGFILE"
	echo ""
done


