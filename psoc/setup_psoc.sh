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

urlquote()
{
	python -c "import urllib;print urllib.quote('$1', safe='')"
}

typedef_values_tag=`urlquote "typedef values"`
typedef_dbtype_tag=`urlquote "typedef dbtype"`
typedef_descriptions_tag=`urlquote "typedef description"`

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

tagdef()
{
   tag_names[${#tag_names[*]}]=`urlquote "$1"`
   tag_dbtypes[${#tag_dbtypes[*]}]=`urlquote "$2"`
   tag_multivalues[${#tag_multivalues[*]}]="$3"
   tag_require[${#tag_multivalues[*]}]="$4"
}

# Login

rm -f cookiefile
curl -b cookiefile -c cookiefile -s -S -k -d username=${USERNAME} -d password=${PASSWORD} https://${TARGET}/webauthn/login

# Define the type definitions

#	TYPENAME		DBTYPE	DESCRIPTION		VALUES
typedef	'Material Source'	text	'Material Source'	'Cell Cell' 'Mouse Mouse'
typedef	'Drug'			text	'Drug'			'CTX CTX'
typedef	'Drug Source'		text	'Drug Source'		'Sigma Sigma'
typedef	'Experimentalist'	text	'Experimentalist'	'Fred%20Casely Fred Casely'

# Define the tags definitions

#	TAGNAME						TYPE			MULTIVAL	REQUIRED
tagdef	'Drug'						'Drug'			false		true
tagdef	'Drug Source'					'Drug Source'		false		true
tagdef	'Protocol Nm'					text			false		true
tagdef	'Protocol Date'					date			false		true
tagdef	'Protocol Version'				int8			false		true
tagdef	'Experiment Date'				date			false		true
tagdef	'Experimentalist'				'Experimentalist'	false		true
tagdef	'Phone'						text			false		true
tagdef	'Email'						text			false		true
tagdef	'Lab Book #'					int8			false		true
tagdef	'Page Number #'					int8			false		true
tagdef	'Material Source'				'Material Source'	false		true
tagdef	'Values of Internal Standards'			text			false		true
tagdef	'Calibration Values & Parameters'		text			false		true
tagdef	'Machine Parameters'				text			false		true
tagdef	'Nutrient Conditions'				text			false		true
tagdef	'Growth Media'					text			false		true
tagdef	'Feeder Cells'					text			false		true
tagdef	'CO2 Concentration'				int8			false		true
tagdef	'O2 Concentration'				int8			false		true
tagdef	'Serum Lot'					int8			false		true
tagdef	'Serum Source'					text			false		true
tagdef	'Serum Percentage'				int8			false		true
tagdef	'Serum Type'					text			false		true
tagdef	'Passage Number'				int8			false		true
tagdef	'Added Growth Factors'				text			false		true
tagdef	'Confluence Number'				int8			false		true
tagdef	'Pressure'					int8			false		true
tagdef	'pH'						text			false		true
tagdef	'Experiment Geometry'				text			false		true
tagdef	'Proliferation Rate'				int8			false		true
tagdef	'Mouse Identifier'				text			false		true
tagdef	'Mouse Age (start of experiment)'		int8			false		true
tagdef	'Time since start of experiment'		int8			false		true
tagdef	'Weight'					int8			false		true
tagdef	'Drug Treatment Regimen'			text			false		true
tagdef	'Cancer Model'					text			false		true
tagdef	'Tumor Injection Protocol'			text			false		true
tagdef	'Cage Number'					int8			false		true
tagdef	'Number Cells Injected'				int8			false		true
tagdef	'Serum Draw Researcher'				text			false		true
tagdef	'Serum Draw Protocol'				text			false		true
tagdef	'Draw Volume'					text			false		true
tagdef	'Organ Harvest Protocol'			text			false		true
tagdef	'Organ Type'					text			false		true
tagdef	'Organ Preservation'				text			false		true
tagdef	'Window Chamber Placement'			text			false		true
tagdef	'Window Chamber Size'				int8			false		true
tagdef	'Imaging Reagents'				text			false		true
tagdef	'Tumor Shape / gross morphology'		text			false		true
tagdef	'What is outside the window?'			text			false		true
tagdef	'Chip Identifier'				text			false		true
tagdef	'DNA Sequence for GOI'				text			false		true
tagdef	'AB Vendors'					text			false		true
tagdef	'AB Catalog #'					int8			false		true
tagdef	'AB Lot #'					int8			false		true
tagdef	'Equipment & Operating Conditions'		text			false		true
tagdef	'Recent QC Information'				text			false		true
tagdef	'Cell Images'					text			false		true


# Define the tags

for ((  i = 0 ;  i < "${#tag_names[*]}";  i++  ))
do
	curl -b cookiefile -c cookiefile -s -S -k -X PUT "https://${TARGET}/tagfiler/tagdef/${tag_names[i]}?typestr=${tag_dbtypes[i]}&multivalue=${tag_multivalues[i]}&readpolicy-1=subject&writepolicy-1=subject"
done

# Set the applet tags

applet_tags=`urlquote "_cfg_applet tags"`
tags=${tag_names[0]}

for ((  i = 1 ;  i < "${#tag_names[*]}";  i++  ))
do
	tags=${tags},${tag_names[i]}
done

curl -b cookiefile -c cookiefile -s -S -k -X PUT "https://${TARGET}/tagfiler/tags/config=tagfiler(${applet_tags}=${tags})"

# Set the applet required tags

applet_required_tags=`urlquote "_cfg_applet tags require"`
tags=""

for ((  i = 0 ;  i < "${#tag_names[*]}";  i++  ))
do
	if [[ ${tag_require[i]} -eq "true" ]]
	then
		if [[ -n ${tags} ]]
		then
			tags=${tags},
		fi
		tags=${tags}${tag_names[i]}
	fi
done

curl -b cookiefile -c cookiefile -s -S -k -X PUT "https://${TARGET}/tagfiler/tags/config=tagfiler(${applet_required_tags}=${tags})"


