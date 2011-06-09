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
#	<user1>				- authentication user1
#	<password1>			- authentication password for user1
#	<user2>				- authentication user2
#	<password2>			- authentication password for user2
#	<file>				- the path of the file to be uploaded
#	<tagfiler>			- the service prefix
#	<logfile>			- the path of the log file
#	<deletefile>		- the path of the file to delete the defined users tags

echo "#!/bin/sh"
echo ""

hostname=|the service hostname|
user1=|the user1|
password1=|password for user1|
user2=|the user2|
password2=|password for user2|
file=|the path of the file to be uploaded|
tagfiler=|the service prefix|
logfile=|the path of the log file|
deletefile=|the path of the file to delete the defined users tags|

user1cookiefile="$user1"cookiefile
user2cookiefile="$user2"cookiefile

echo HOST=https://$hostname
echo LOGIN=https://$hostname/webauthn/login
echo AUTHENTICATION_USER1=\"-d username=$user1 -d password=$password1\"
echo AUTHENTICATION_USER2=\"-d username=$user2 -d password=$password2\"
echo USER1_COOKIE=\"-b $user1cookiefile -c $user1cookiefile\"
echo USER2_COOKIE=\"-b $user2cookiefile -c $user2cookiefile\"
echo FILE=\"$file\"
echo URL=http://www.yahoo.com
echo SVCPREFIX=$tagfiler
echo ""

echo COMMON_OPTIONS=\"-s -S -k\"
echo LOGFILE=$logfile
echo DELETEFILE=$deletefile
echo DATASET1=Spectrophotometry
echo DATASET2=Retinoblastoma
echo ""

echo "echo \"#!/bin/sh\" > \$DELETEFILE"
echo "echo \"\" >> \$DELETEFILE"

echo "echo \"HOST=https://$hostname\" >> \$DELETEFILE"
echo "echo \"LOGIN=https://$hostname/webauthn/login\" >> \$DELETEFILE"
echo "echo \"AUTHENTICATION_USER1=\\\"-d username=$user1 -d password=$password1\\\"\" >> \$DELETEFILE"
echo "echo \"AUTHENTICATION_USER2=\\\"-d username=$$user2 -d password=$password2\\\"\" >> \$DELETEFILE"
echo "echo \"USER1_COOKIE=\\\"-b $user1cookiefile -c $user1cookiefile\\\"\" >> \$DELETEFILE"
echo "echo \"USER2_COOKIE=\\\"-b $user2cookiefile -c $user2cookiefile\\\"\" >> \$DELETEFILE"
echo "echo \"FILE=$file\" >> \$DELETEFILE"
echo "echo \"URL=http://www.yahoo.com\" >> \$DELETEFILE"
echo "echo \"SVCPREFIX=$tagfiler\" >> \$DELETEFILE"
echo "echo \"\" >> \$DELETEFILE"

echo "echo \"COMMON_OPTIONS=\\\"-s -S -k\\\"\" >> \$DELETEFILE"
echo "echo \"LOGFILE=$logfile\" >> \$DELETEFILE"
echo "echo \"DELETEFILE=$deletefile\" >> \$DELETEFILE"
echo "echo \"DATASET1=Spectrophotometry\" >> \$DELETEFILE"
echo "echo \"DATASET2=Retinoblastoma\" >> \$DELETEFILE"
echo "echo \"\" >> \$DELETEFILE"
echo ""
echo "echo \"curl \$USER1_COOKIE \$COMMON_OPTIONS \$AUTHENTICATION_USER1 \$LOGIN\" >> \$DELETEFILE"
echo "echo \"echo \\\"\\\"\" >> \$DELETEFILE"
echo "echo \"\" >> \$DELETEFILE"
echo ""

echo "echo \"curl \$USER2_COOKIE \$COMMON_OPTIONS \$AUTHENTICATION_USER2 \$LOGIN\" >> \$DELETEFILE"
echo "echo \"echo \\\"\\\"\" >> \$DELETEFILE"
echo "echo \"\" >> \$DELETEFILE"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \\\"\$HOST/\$SVCPREFIX/tagdef/tag_no_content_read_${i}_write_${j}\\\"\" >> \$DELETEFILE"
		echo "echo \"\" >> \$DELETEFILE"
		echo ""
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\\\"\" >> \$DELETEFILE"
		echo "echo \"\" >> \$DELETEFILE"
		echo ""
	done
done

echo "START=\$(date +%s)"
echo ""

echo "date > \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "echo \"Authenticate \\\"\$AUTHENTICATION_USER1\\\"\" >> \$LOGFILE"
echo "echo \"curl \$USER1_COOKIE \$COMMON_OPTIONS \$AUTHENTICATION_USER1 \$LOGIN\" >> \$LOGFILE"
echo "curl \$USER1_COOKIE \$COMMON_OPTIONS \$AUTHENTICATION_USER1 \$LOGIN >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "echo \"Authenticate \\\"\$AUTHENTICATION_USER2\\\"\" >> \$LOGFILE"
echo "echo \"curl \$USER2_COOKIE \$COMMON_OPTIONS \$AUTHENTICATION_USER2 \$LOGIN\" >> \$LOGFILE"
echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \$AUTHENTICATION_USER2 \$LOGIN >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# Tags Actions"
echo ""

echo "# Define the tags with POST"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\\\" \\\"\$HOST/\$SVCPREFIX/tagdef\\\"\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags by user \"$user1\""
echo "echo \"List the tags by user \\\"$user1\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"$user2\""
echo "echo \"List the tags by user \\\"$user2\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tag definitions by user \"$user1\""
echo ""

echo "echo \"List the tag definitions by user \\\"$user1\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tag definitions by user \"$user2\""
echo ""

echo "echo \"List the tag definitions by user \\\"$user2\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Delete the tags with POST"
echo ""

echo "echo \"Delete \\\"tag_read_anonymous_write_anonymous\\\" tag by user \\\"$user1\\\" with POST\" >> \$LOGFILE"
echo "echo \"curl \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=ConfirmDelete\\\" \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_anonymous_write_anonymous\\\"\" >> \$LOGFILE"
echo "curl \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=ConfirmDelete\" \"\$HOST/\$SVCPREFIX/tagdef/tag_read_anonymous_write_anonymous\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "echo \"Delete the tag definitions with POST\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ ${i} != "anonymous" ] || [ ${j} != "anonymous" ]; then
			echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=ConfirmDelete\\\" \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=ConfirmDelete\" \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# List the tags by user \"$user1\""
echo "echo \"List the tags by user \\\"$user1\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"$user2\""
echo "echo \"List the tags by user \\\"$user2\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# Define the tags with PUT"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}?typestr=text&multivalue=true&readpolicy=${i}&writepolicy=${j}\\\"\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}?typestr=text&multivalue=true&readpolicy=${i}&writepolicy=${j}\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags by user \"$user1\""
echo "echo \"List the tags by user \\\"$user1\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"$user2\""
echo "echo \"List the tags by user \\\"$user2\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tag definitions by user \"$user1\""
echo ""

echo "echo \"List the tag definitions by user \\\"$user1\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tag definitions by user \"$user2\""
echo ""

echo "echo \"List the tag definitions by user \\\"$user2\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Tag \\\"tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\\\"\" >> \$LOGFILE"
		echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_$j\" >> \$LOGFILE"
		echo "echo -e \"\\n\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Delete the tags with DELETE"
echo ""

echo "echo \"Delete \\\"tag_read_anonymous_write_anonymous\\\" tag by user \\\"$user2\\\" with DELETE\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "echo \"curl \$USER2_COOKIE \$COMMON_OPTIONS -X DELETE  \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_anonymous_write_anonymous\\\"\" >> \$LOGFILE"
echo "curl \$USER2_COOKIE \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_anonymous_write_anonymous\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "echo \"Delete the tag definitions with DELETE\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ ${i} != "anonymous" ] || [ ${j} != "anonymous" ]; then
			echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# List the tags by user \"$user1\""
echo "echo \"List the tags by user \\\"$user1\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"$user2\""
echo "echo \"List the tags by user \\\"$user2\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# Define the tags with POST"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\\\" \\\"\$HOST/\$SVCPREFIX/tagdef\\\"\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Define the tag readers and writers with POST"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Define read user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-read%20users=true&val-read%20users=technician1&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-read%20users=true&val-read%20users=technician1&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define read user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-read%20users=true&val-read%20users=technician2&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-read%20users=true&val-read%20users=technician2&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Define write user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-write%20users=true&val-write%20users=technician1&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-write%20users=true&val-write%20users=technician1&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define write user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-write%20users=true&val-write%20users=technician2&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-write%20users=true&val-write%20users=technician2&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"$user2\""
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"$user2\\\"\" >> \$LOGFILE"
			echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Delete the tag readers and writers with POST"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Delete read user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag=read%20users&value=technician1&action=delete\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag=read%20users&value=technician1&action=delete\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete read user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag=read%20users&value=technician2&action=delete\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag=read%20users&value=technician2&action=delete\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Delete write user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag=write%20users&value=technician1&action=delete\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag=write%20users&value=technician1&action=delete\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete write user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag=write%20users&value=technician2&action=delete\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag=write%20users&value=technician2&action=delete\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"$user2\""
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"$user2\\\"\" >> \$LOGFILE"
			echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Define the tag readers and writers with PUT"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Define read user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician1)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician1)\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define read user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician2)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician2)\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Define write user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician1)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician1)\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define write user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with PUT\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician2)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X PUT \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician2)\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"$user2\""
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"$user2\\\"\" >> \$LOGFILE"
			echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Delete the tag readers and writers with DELETE"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Delete read user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician1)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician1)\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete read user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician2)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(read%20users=technician2)\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Delete write user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician1)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician1)\" >> \$LOGFILE"
			echo ""
			echo "echo \"Delete write user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician2)\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}(write%20users=technician2)\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Display the tag readers and writers with user \"$user2\""
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ] || [ "$j" == "tag" ]
		then
			echo "echo \"List read/write users for \\\"tag_read_${i}_write_${j}\\\" tag with user \\\"$user2\\\"\" >> \$LOGFILE"
			echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\" | xsltproc --html dataset.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
			echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" | xsltproc --html dataset.xslt - | grep  \"( \" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "echo \"Delete the tag definitions with DELETE\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
		echo ""
	done
done

echo "# List the tags by user \"$user1\""
echo "echo \"List the tags by user \\\"$user1\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# List the tags by user \"$user2\""
echo "echo \"List the tags by user \\\"$user2\\\"\" >> \$LOGFILE"
echo "echo \"curl  \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tagdef\\\" | xsltproc --html tagdef.xslt - | grep \\\"( \\\"\" >> \$LOGFILE"
echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tagdef\" | xsltproc --html tagdef.xslt - | grep  \"( \" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "# Define the tags with POST"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Define \\\"tag_no_content_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag-1=tag_no_content_read_${i}_write_${j}&type-1=empty&multivalue-1=false&readpolicy-1=${i}&writepolicy-1=${j}&action=add\\\" \\\"\$HOST/\$SVCPREFIX/tagdef\\\"\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag-1=tag_no_content_read_${i}_write_${j}&type-1=empty&multivalue-1=false&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
		echo "echo \"Define \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\\\" \\\"\$HOST/\$SVCPREFIX/tagdef\\\"\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"tag-1=tag_read_${i}_write_${j}&type-1=text&multivalue-1=true&readpolicy-1=${i}&writepolicy-1=${j}&action=add\" \"\$HOST/\$SVCPREFIX/tagdef\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Define the tag readers and writers with POST"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		if [ "$i" == "tag" ]
		then
			echo "echo \"Define read user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-read%20users=true&val-read%20users=technician1&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-read%20users=true&val-read%20users=technician1&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define read user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-read%20users=true&val-read%20users=technician2&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-read%20users=true&val-read%20users=technician2&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
		if [ "$j" == "tag" ]
		then
			echo "echo \"Define write user \\\"technician1\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-write%20users=true&val-write%20users=technician1&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-write%20users=true&val-write%20users=technician1&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Define write user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-write%20users=true&val-write%20users=technician2&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-write%20users=true&val-write%20users=technician2&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
			echo ""
		fi
	done
done

echo "# Adding Dataset Tags"
echo ""

echo "echo \"Define \\\"\$DATASET1\\\" dataset with PUT\"  >> \$LOGFILE"
echo "date >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -T \\\"\$FILE\\\" \\\"\$HOST/\$SVCPREFIX/file/name=\$DATASET1\\\"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -T \"\$FILE\" \"\$HOST/\$SVCPREFIX/file/name=\$DATASET1\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "date >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo ""

echo "echo \"Add \\\"read users\\\" tag to dataset \\\"\$DATASET1\\\" with value \\\"*\\\" using POST\"  >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=put&set-read%20users=true&val-read%20users=*\\\" \\\"\$HOST/\$SVCPREFIX/tags/name=\$DATASET1\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=put&set-read%20users=true&val-read%20users=*\" \"\$HOST/\$SVCPREFIX/tags/name=\$DATASET1\" >> \$LOGFILE"
echo ""

echo "echo \"Define \\\"\$DATASET2\\\" dataset with url POST\"  >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=put&url=\$URL\\\" \\\"\$HOST/\$SVCPREFIX/file/name=\$DATASET2\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=put&url=\$URL\" \"\$HOST/\$SVCPREFIX/file/name=\$DATASET2\" >> \$LOGFILE"
echo ""

echo "echo \"Add \\\"read users\\\" tag to dataset \\\"\$DATASET2\\\" with value \\\"*\\\" using POST\"  >> \$LOGFILE"
echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=put&set-read%20users=true&val-read%20users=*\\\" \\\"\$HOST/\$SVCPREFIX/tags/name=\$DATASET2\\\"\" >> \$LOGFILE"
echo "echo \"\" >> \$LOGFILE"
echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=put&set-read%20users=true&val-read%20users=*\" \"\$HOST/\$SVCPREFIX/tags/name=\$DATASET2\" >> \$LOGFILE"
echo ""

echo "# Add values to the tags with POST"
echo ""

for k in Spectrophotometry Retinoblastoma
do
	for i in anonymous subject subjectowner tag users
	do
		for j in anonymous subject subjectowner tag users
		do
			echo "echo \"Add \\\"tag_no_content_read_${i}_write_${j}\\\" tag to dataset \\\"${k}\\\" using POST\"  >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=put&set-tag_no_content_read_${i}_write_${j}=true\\\" \\\"\$HOST/\$SVCPREFIX/tags/name=${k}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=put&set-tag_no_content_read_${i}_write_${j}=true\" \"\$HOST/\$SVCPREFIX/tags/name=${k}\" >> \$LOGFILE"
			echo ""
			echo "echo \"Add \\\"tag_read_${i}_write_${j}\\\" tag to dataset \\\"${k}\\\" with values \\\"tag_read_${i}_write_${j}_VALUE1\\\" and \\\"tag_read_${i}_write_${j}_VALUE2\\\" using POST\"  >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=put&set-tag_read_${i}_write_${j}=true&val-tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1\\\" \\\"\$HOST/\$SVCPREFIX/tags/name=${k}\\\"\" >> \$LOGFILE"
			echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"action=put&set-tag_read_${i}_write_${j}=true&val-tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE2\\\" \\\"\$HOST/\$SVCPREFIX/tags/name=${k}\\\"\" >> \$LOGFILE"
			echo "echo \"\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=put&set-tag_read_${i}_write_${j}=true&val-tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1\" \"\$HOST/\$SVCPREFIX/tags/name=${k}\" >> \$LOGFILE"
			echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"action=put&set-tag_read_${i}_write_${j}=true&val-tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE2\" \"\$HOST/\$SVCPREFIX/tags/name=${k}\" >> \$LOGFILE"
			echo ""
			if [ "$i" == "tag" ]
			then
				echo "echo \"Define read user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
				echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-read%20users=true&val-read%20users=technician2&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
				echo "echo \"\" >> \$LOGFILE"
				echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-read%20users=true&val-read%20users=technician2&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
				echo ""
			fi
			if [ "$j" == "tag" ]
			then
				echo "echo \"Define write user \\\"technician2\\\" for \\\"tag_read_${i}_write_${j}\\\" tag with POST\" >> \$LOGFILE"
				echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \\\"set-write%20users=true&val-write%20users=technician2&action=put\\\" \\\"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
				echo "echo \"\" >> \$LOGFILE"
				echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -d \"set-write%20users=true&val-write%20users=technician2&action=put\" \"\$HOST/\$SVCPREFIX/tags/tagdef=tag_read_${i}_write_${j}\" >> \$LOGFILE"
				echo ""
			fi
		done
	done
done

echo "# Get dataset tags"
echo ""

for k in Spectrophotometry Retinoblastoma
do
	echo "echo \"Fetch dataset \\\"${k}\\\" tags\"  >> \$LOGFILE"
	echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/name=${k}\\\"  | xsltproc --html alltags.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
	echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/name=${k}\"  | xsltproc --html alltags.xslt - | grep  \"( \" >> \$LOGFILE"
	echo "echo \"\" >> \$LOGFILE"
	echo ""
	echo "echo \"Fetch dataset \\\"${k}\\\" tags by user \\\"$user2\\\"\"  >> \$LOGFILE"
	echo "echo \"curl \$USER2_COOKIE \$COMMON_OPTIONS \\\"\$HOST/\$SVCPREFIX/tags/name=${k}\\\"  | xsltproc --html alltags.xslt - | grep  \\\"( \\\"\" >> \$LOGFILE"
	echo "curl \$USER2_COOKIE \$COMMON_OPTIONS \"\$HOST/\$SVCPREFIX/tags/name=${k}\"  | xsltproc --html alltags.xslt - | grep  \"( \" >> \$LOGFILE"
	echo "echo \"\" >> \$LOGFILE"
	echo ""
done

echo "# Queries"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Query for \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE1\\\" AND \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE2\\\"\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -H \\\"Accept: text/uri-list\\\" -X GET \\\"\$HOST/\$SVCPREFIX/query/tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1;tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE2\\\"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1;tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE2\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
		echo "echo \"Query for \\\"tag_no_content_read_${i}_write_${j}\\\" EXISTS\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -H \\\"Accept: text/uri-list\\\" -X GET \\\"\$HOST/\$SVCPREFIX/query/tag_no_content_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_no_content_read_${i}_write_${j}\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
		echo "echo \"Query for \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE1\\\" AND \\\"tag_read_${i}_write_${j}\\\" == \\\"tag_read_${i}_write_${j}_VALUE2\\\" for user \\\"$user2\\\"\" >> \$LOGFILE"
		echo "echo \"curl \$USER2_COOKIE \$COMMON_OPTIONS -H \\\"Accept: text/uri-list\\\" -X GET \\\"\$HOST/\$SVCPREFIX/query/tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1;tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE2\\\"\" >> \$LOGFILE"
		echo "curl \$USER2_COOKIE \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE1;tag_read_${i}_write_${j}=tag_read_${i}_write_${j}_VALUE2\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
		echo "echo \"Query for \\\"tag_no_content_read_${i}_write_${j}\\\" EXISTS for user \\\"$user2\\\"\" >> \$LOGFILE"
		echo "echo \"curl \$USER2_COOKIE \$COMMON_OPTIONS -H \\\"Accept: text/uri-list\\\" -X GET \\\"\$HOST/\$SVCPREFIX/query/tag_no_content_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
		echo "curl \$USER2_COOKIE \$COMMON_OPTIONS -H \"Accept: text/uri-list\" -X GET \"\$HOST/\$SVCPREFIX/query/tag_no_content_read_${i}_write_${j}\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Delete the tag definitions"
echo ""

for i in anonymous subject subjectowner tag users
do
	for j in anonymous subject subjectowner tag users
	do
		echo "echo \"Delete \\\"tag_no_content_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \\\"\$HOST/\$SVCPREFIX/tagdef/tag_no_content_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_no_content_read_${i}_write_${j}\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
		echo "echo \"Delete \\\"tag_read_${i}_write_${j}\\\" tag with DELETE\" >> \$LOGFILE"
		echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \\\"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\\\"\" >> \$LOGFILE"
		echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE  \"\$HOST/\$SVCPREFIX/tagdef/tag_read_${i}_write_${j}\" >> \$LOGFILE"
		echo "echo \"\" >> \$LOGFILE"
		echo ""
	done
done

echo "# Delete the datasets"
echo ""

for k in Spectrophotometry Retinoblastoma
do
	echo "echo \"Delete \\\"${k}\\\" dataset with DELETE\"  >> \$LOGFILE"
	echo "echo \"curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \\\"\$HOST/\$SVCPREFIX/file/name=${k}\\\"\" >> \$LOGFILE"
	echo "curl  \$USER1_COOKIE \$COMMON_OPTIONS -X DELETE \"\$HOST/\$SVCPREFIX/file/name=${k}\" >> \$LOGFILE"
	echo "echo \"\" >> \$LOGFILE"
	echo ""
done
