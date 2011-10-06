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

TARGET=${TARGET:-basin.isi.edu}
USERNAME=${USERNAME:-$(whoami)}
PASSWORD=${PASSWORD:-just4demo}

tag_names=()
tag_dbtypes=()
tag_multivalues=()
tag_require=()
group_names=()

addGroup()
{
	local found="false"
	local i
	for ((  i = 0 ;  i < "${#group_names[*]}";  i++  ))
	do
		if [[ ${group_names[i]} == "$1" ]]
		then
			found="true"
			break
		fi
	done
	if [[ ${found} == "false" ]]
	then
		group_names[${#group_names[*]}]="$1"
	fi
}

isRequiredTag()
{
	local found="false"
	local i
	for ((  i = 0 ;  i < "${#tag_require[*]}";  i++  ))
	do
		if [[ "${tag_require[i]}" == "$1" ]]
		then
			found="true"
			break
		fi
	done
	echo ${found}
}

urlquote()
{
	python -c "import urllib;print urllib.quote('$1', safe='')"
}

typedef_values_tag=`urlquote "typedef values"`
typedef_dbtype_tag=`urlquote "typedef dbtype"`
typedef_descriptions_tag=`urlquote "typedef description"`
applet_tags=`urlquote "_cfg_applet tags"`
applet_required_tags=`urlquote "_cfg_applet tags require"`
PSOC_tagfiler_admin=`urlquote "PSOC tagfiler admin"`
read_users=`urlquote "read users"`

typedef()
{
	# get the URL for the new id
	local url=`curl -b cookiefile -c cookiefile -s -S -k -d action=post "https://${TARGET}/tagfiler/file" | sed 's/file\/id/tags\/id/g'`
	local name=`urlquote "$1"`
	local dbtype=`urlquote "$2"`
	local description=`urlquote "$3"`
	shift 3
	local values=""
	while (( "$#" )); do
		if [[ -n ${values} ]]
		then
			values=${values},
		fi
		values=${values}`urlquote "$1"`
		shift
	done
	local enum=""
	if [[ -n ${values} ]]
	then
		enum=";${typedef_values_tag}=${values}"
	fi
	curl -b cookiefile -c cookiefile -s -S -k -X PUT "${url}(typedef=${name}${enum};${typedef_descriptions_tag}=${description};${typedef_dbtype_tag}=${dbtype})"
}

configdef()
{
	# get the URL for the new id
	local url=`curl -b cookiefile -c cookiefile -s -S -k -d action=post "https://${TARGET}/tagfiler/file" | sed 's/file\/id/tags\/id/g'`
	local name=`urlquote "$1"`
	local values=""
	local required_values=""
	local tags="\${#tag_groups_${name}[*]}"
	eval "count=${tags}"
	local i
	local isRequired
	for ((  i = 0 ;  i < ${count};  i++  ))
	do
		if [[ -n ${values} ]]
		then
			values=${values},
		fi
		local tag="\${tag_groups_$name[i]}"
		eval "tag=${tag}"
		values=${values}`urlquote "${tag}"`
		isRequired=$(isRequiredTag "${tag}")
		if [[ ${isRequired} == "true" ]]
		then
			if [[ -n ${required_values} ]]
			then
				required_values=${required_values},
			fi
			required_values=${required_values}`urlquote "${tag}"`
		fi
	done
	local enum=""
	local required_enum=""
	if [[ -n ${values} ]]
	then
		enum=";${applet_tags}=${values}"
	fi
	if [[ -n ${required_values} ]]
	then
		required_enum=";${applet_required_tags}=${required_values}"
	fi
	curl -b cookiefile -c cookiefile -s -S -k -X PUT "${url}(config=${name}${enum}${required_enum};${read_users}=*)"

	case "${name}" in
	    RP?)
		offset=${name:2}
		;;
	    *)
		offset=0
		;;
	esac

	curl -b cookiefile -c cookiefile -s -S -k -X POST "https://${TARGET}/tagfiler/file/name=Upload%20${name}%20data;url=$(urlquote "https://${TARGET}/tagfiler/study?action=upload&type=${name}");list%20on%20homepage;homepage%20order=$(( 120 + $offset ));read%20users=%2A"
	
}

tagdef()
{
	local name="$1"
	tag_names[${#tag_names[*]}]=`urlquote "$1"`
	tag_dbtypes[${#tag_dbtypes[*]}]=`urlquote "$2"`
	tag_multivalues[${#tag_multivalues[*]}]="$3"
	if [[ "$4" == "true" ]]
	then
		tag_require[${#tag_require[*]}]="$1"
	fi
	shift 4
	while [ "$1" ]
	do
		addGroup "$1"
		eval "tag_groups_$1[\${#tag_groups_$1[*]}]=\"${name}\""
		shift 1
	done
}

# Login

rm -f cookiefile
curl -b cookiefile -c cookiefile -s -S -k -d username=${USERNAME} -d password=${PASSWORD} https://${TARGET}/webauthn/login


# Templates for defining types and tags
#			TYPENAME			DBTYPE	DESCRIPTION			VALUES
#typedef	'Material Source'	text	'Material Source'	'Cell Cell' 'Mouse Mouse'
#typedef	'Drug'				text	'Drug'				'CTX CTX'
#typedef	'Experimentalist'	text	'Experimentalist'	'Fred%20Casely Fred Casely'
#		TAGNAME								TYPE				MULTIVAL	REQUIRED	GROUPS
#tagdef	'Protocol Nm'						text				false		true		PSOC
#tagdef	'Experimentalist'					'Experimentalist'	false		true		PSOC


# Define the tags definitions

#		TAGNAME								TYPE	MULTIVAL	REQUIRED	GROUPS
tagdef	'Drug'								text	false		true		PSOC RP1 RP3 RP4
tagdef	'Drug Source'						text	false		true		PSOC RP1 RP3 RP4
tagdef	'Protocol Nm'						text	false		true		PSOC RP1 RP3 RP4
tagdef	'Protocol Date'						date	false		true		PSOC RP1 RP3 RP4
tagdef	'Protocol Version'					int8	false		true		PSOC RP1 RP3 RP4
tagdef	'Experiment Date'					date	false		true		PSOC RP1 RP3 RP4
tagdef	'Experimentalist'					text	false		true		PSOC RP1 RP3 RP4
tagdef	'Phone'								text	false		true		PSOC RP1 RP3 RP4
tagdef	'Email'								text	false		true		PSOC RP1 RP3 RP4
tagdef	'Lab Book #'						int8	false		true		PSOC RP1 RP3 RP4
tagdef	'Page Number #'						int8	false		true		PSOC RP1 RP3 RP4
tagdef	'Material Source'					text	false		true		PSOC RP1 RP3 RP4
tagdef	'Values of Internal Standards'		text	false		true		PSOC RP1 RP3 RP4
tagdef	'Calibration Values & Parameters'	text	false		true		PSOC RP1 RP3 RP4
tagdef	'Machine Parameters'				text	false		true		RP1
tagdef	'Nutrient Conditions'				text	false		true		RP1
tagdef	'Growth Media'						text	false		true		RP1
tagdef	'Feeder Cells'						text	false		true		RP1
tagdef	'CO2 Concentration'					int8	false		true		RP1
tagdef	'O2 Concentration'					int8	false		true		RP1
tagdef	'Serum Lot'							int8	false		true		RP1
tagdef	'Serum Source'						text	false		true		RP1
tagdef	'Serum Percentage'					int8	false		true		RP1
tagdef	'Serum Type'						text	false		true		RP1
tagdef	'Passage Number'					int8	false		true		RP1
tagdef	'Added Growth Factors'				text	false		true		RP1
tagdef	'Confluence Number'					int8	false		true		RP1
tagdef	'Pressure'							int8	false		true		RP1
tagdef	'pH'								text	false		true		RP1
tagdef	'Experiment Geometry'				text	false		true		RP1
tagdef	'Proliferation Rate'				int8	false		true		RP1
tagdef	'Mouse Identifier'					text	false		true		RP3 RP4
tagdef	'Mouse Age (start of experiment)'	int8	false		true		RP3 RP4
tagdef	'Time since start of experiment'	int8	false		true		RP3 RP4
tagdef	'Weight'							int8	false		true		RP3 RP4
tagdef	'Drug Treatment Regimen'			text	false		true		RP3 RP4
tagdef	'Cancer Model'						text	false		true		RP3 RP4
tagdef	'Tumor Injection Protocol'			text	false		true		RP3 RP4
tagdef	'Cage Number'						int8	false		true		RP3 RP4
tagdef	'Number Cells Injected'				int8	false		true		RP3 RP4
tagdef	'Serum Draw Researcher'				text	false		true		RP3 RP4
tagdef	'Serum Draw Protocol'				text	false		true		RP3 RP4
tagdef	'Draw Volume'						text	false		true		RP3 RP4
tagdef	'Organ Harvest Protocol'			text	false		true		RP3 RP4
tagdef	'Organ Type'						text	false		true		RP3 RP4
tagdef	'Organ Preservation'				text	false		true		RP3 RP4
tagdef	'Window Chamber Placement'			text	false		true		RP3
tagdef	'Window Chamber Size'				int8	false		true		RP3
tagdef	'Imaging Reagents'					text	false		true		RP3
tagdef	'Tumor Shape / gross morphology'	text	false		true		RP3
tagdef	'What’s outside the window?'		text	false		true		RP3
tagdef	'Chip Identifier'					text	false		true		RP4
tagdef	'DNA Sequence for GOI'				text	false		true		RP4
tagdef	'AB Vendors'						text	false		true		RP4
tagdef	'AB Catalog #'						int8	false		true		RP4
tagdef	'AB Lot #’s'						int8	false		true		RP4
tagdef	'Equipment & Operating Conditions'	text	false		true		RP4
tagdef	'Recent QC Information'				text	false		true		RP1
tagdef	'Cell Images'						text	false		true		RP1

# Define the tags

for ((  i = 0 ;  i < "${#tag_names[*]}";  i++  ))
do
	curl -b cookiefile -c cookiefile -s -S -k -X PUT "https://${TARGET}/tagfiler/tagdef/${tag_names[i]}?typestr=${tag_dbtypes[i]}&multivalue=${tag_multivalues[i]}&readpolicy-1=subject&writepolicy-1=subject"
	curl -b cookiefile -c cookiefile -s -S -k -X PUT "https://${TARGET}/tagfiler/tags/tagdef=${tag_names[i]}(owner=${PSOC_tagfiler_admin})"
done

# Define the group configurations

for ((  i = 0 ;  i < "${#group_names[*]}";  i++  ))
do
	configdef ${group_names[i]}
done
