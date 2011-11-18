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

## Types and Tags for NEI MISD/DEI demo...

homelinks=(
$(dataset "New image studies" url 'Image%20Set;Downloaded:absent:?view=study%20tags' "${admin}" "${downloader}")
$(dataset "Previous image studies" url 'Image%20Set;Downloaded?view=study%20tags' "${admin}" "${downloader}")
$(dataset "All image studies" url 'Image%20Set?view=study%20tags' "${admin}" "${downloader}")
)

i=0
while [[ $i -lt "${#homelinks[*]}" ]]
do
   tag "${homelinks[$i]}" "list on homepage"
   tag "${homelinks[$i]}" "homepage order" int "$i"
   i=$(( $i + 1 ))
done


tagdef "Downloaded"   ""          ""      tag         tag        false
tagacl "Downloaded" read "${downloader}"
tagacl "Downloaded" write "${downloader}"

dataset "study tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/study%20tags" "${admin}" "*"
dataset "fundus tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/fundus%20tags" "${admin}" "*"
dataset "fundus brief tags" url "https://${HOME_HOST}/${SVCPREFIX}/tags/fundus%20brief%20tags" "${admin}" "*"

modtagdef()
{
   local modality="$1"
   local tagname="$2"
   shift 2
   tagdef "$tagname" "$@"
   tag "$modality tags" "_cfg_file list tags" tagname "$tagname"
   tag "$modality tags" "_cfg_tag list tags" tagname "$tagname"
   tagacl "$tagname" read "${downloader}"
   tagacl "$tagname" write "${grader}"
}

typedef Modality            text 'Modality' 'fundus fundus'
typedef 'Study Name'        text 'Study Name' 'CHES CHES' 'MEPED MEPED' 'LALES LALES'

# fundus
typedef '# 0-9'             int8 'Count (0-9)' '0 0' '1 1' '2 2' '3 3' '4 4' '5 5' '6 6' '7 7' '8 8' '9 9'
typedef '# 0-16'            int8 'Count (0-16)' '0 0' '1 1' '2 2' '3 3' '4 4' '5 5' '6 6' '7 7' '8 8' '9 9' '10 10' '11 11' '12 12' '13 13' '14 14' '15 15' '16 16'
typedef 'no/yes'            int8 'Grade (no/yes)' '0 No' '2 Yes'
typedef 'no/yes/CG'         int8 'Grade (no/yes/CG)' '0 No' '2 Yes' '8 CG'
typedef 'Max DRU Size'      int8 'Grade (Max DRU Size)' '0 None' '1 Questionable/HI' '2 <C0' '3 <C1' '4 <C2' '5 C2' '6 Retic' '8 CG'
typedef 'DRU Area'          int8 'Grade (DRU Area)' '0 None/NA' '10 <63 (C0)' '20 <105' '25 <125 (C1)' '30 <250 (C2)' '35 <350 (I2)' '40 <500' '45 <650 (O2)' '50 <0.5 DA' '60 <1 DA' '70 1 DA' '8 CG'
typedef 'Max DRU Type'      int8 'Grade (Max DRU Type)' '0 None' '1 HI' '2 HD' '3 SD' '4 SI/Retic' '8 CG'
typedef 'DRU Grid Type'     int8 'Grade (DRU Grid Type)' '0 Absent' '1 Questionable' '2 Present' '3 Predom/#' '8 CG'
typedef 'Inc Pigment'       int8 'Grade (Inc Pigment)' '0 None' '1 Questionable' '2 <C0' '3 <C1' '4 <C2' '5 <O2' '6 O2' '7 Pig/Other' '8 CG'
typedef 'RPE Depigment'     int8 'Grade (RPE Depigment)' '0 None' '1 Questionable' '20 <C1' '30 <C2' '35 <I2' '40 <O2' '50 <0.5DA' '60 <1DA' '70 1DA' '8 CG'
typedef 'Inc/RPE Lesions'   int8 'Grade (Inc/RPE)' '0 N' '1 Q' '2 CC' '3 CPT' '8 CG'
typedef 'GA/Ex DA Lesions'  int8 'Grade (GA/Ex DA)' '0 N' '1 Q' '2 Y' '3 CC' '4 CPT' '8 CG'
typedef 'Other Lesions'     int8 'Grade (Other w/o PT)' '0 N' '1 Q' '2 Y' '8 CG'
typedef 'Other Lesions +PT' int8 'Grade (Other w/ PT)' '0 N' '1 Q' '2 Y' '3 PT' '8 CG'
typedef 'Diabetic Retinopathy Level' int8 'Grade (Diabetic Retinopathy Level)' '10 DR Abset' '12 Non-Diabetic' '13 Questionable' '14 HE, SE, IRMA w/o MAs' '15 Hem Only w/o MAs' '20 Microaneurysms Only' '31 Mild NPDR' '37 Mild/Moderate NPDR' '43 Moderate NPDR' '47 Moderate/Severe NPDR' '53 Severe NPDR' '60 FP Only' '61 No Ret w/ RX' '62 MAs Only w/ RX' '63 Early NPDR w/ RX' '64 Moderate/Severe NPDR w/ RX' '65 Moderate PDR' '71 DRS HRC' '75 Severe DRS HRC' '81 Advanced PDR' '85 End-Stage PDR' '90 Cannot Grade'

#        TAGNAME                      TYPE   OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR
tagdef   Modality                     text   "${admin}"   tag         tag        false      Modality
tag "fundus tags" "_cfg_file list tags" tagname "Modality"

tagdef   'Study Name'                 text   "${admin}"   tag         tag        false      'Study Name'
tagdef   'Study Participant'          text   "${admin}"   tag         tag        false
tagdef   'Study Date'                 date   "${admin}"   tag         tag        false

for tag in 'Modality' 'Study Name' 'Study Participant' 'Study Date'
do
   tagacl "$tag" read PI "${downloader}"
   tagacl "$tag" write tagger "${coordinator}"
done

# set default applet tags and configure named views too...
cfgtag "applet tags" tagname  "Modality" "Study Name" "Study Participant" "Study Date"
cfgtag "applet tags require" tagname  "Modality" "Study Name" "Study Participant" "Study Date"

for tag in '_cfg_file list tags' '_cfg_file list tags write' '_cfg_applet tags' '_cfg_applet tags require'
do 
   tag 'study tags' "$tag" tagname "Modality" "Study Name" "Study Participant" "Study Date"
done


#         MOD    TAGNAME                      TYPE   OWNER   READPOL     WRITEPOL   MULTIVAL   TYPESTR
modtagdef fundus    'Max DRU Size'               int8   "${admin}"   tag         tag        false      'Max DRU Size'
modtagdef fundus    '# DRU Size Subfields'       int8   "${admin}"   tag         tag        false      '# 0-9'
modtagdef fundus    'DRU Area'                   int8   "${admin}"   tag         tag        false      'DRU Area'
modtagdef fundus    'Max DRU Type'               int8   "${admin}"   tag         tag        false      'Max DRU Type'
modtagdef fundus    '# DRU Type Subfields'       int8   "${admin}"   tag         tag        false      '# 0-9'
modtagdef fundus    'DRU Grid Type'              int8   "${admin}"   tag         tag        false      'DRU Grid Type'
modtagdef fundus    'Inc Pignment'               int8   "${admin}"   tag         tag        false      'Inc Pigment'
modtagdef fundus    'RPE Depigment'              int8   "${admin}"   tag         tag        false      'RPE Depigment'
modtagdef fundus    '# RPE Depigment Subfields'  int8   "${admin}"   tag         tag        false      '# 0-9'

modtagdef fundus    'Inc Pigment CC/CPT'         int8   "${admin}"   tag         tag        false      'Inc/RPE Lesions'
modtagdef fundus    'RPE Depigment CC/CPT'       int8   "${admin}"   tag         tag        false      'Inc/RPE Lesions'

modtagdef fundus    'Geographic Atrophy'         int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'PED/RD'                     int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'SubRet Hem'                 int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'SubRet Scar'                int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'ARM RX'                     int8   "${admin}"   tag         tag        false      'GA/Ex DA Lesions'
modtagdef fundus    'Lesions Summary'            int8   "${admin}"   tag         tag        false      'no/yes/CG'

modtagdef fundus    'GA # DAs in Grid'           int8   "${admin}"   tag         tag        false      '# 0-16'
modtagdef fundus    'Ex # DAs in Grid'           int8   "${admin}"   tag         tag        false      '# 0-16'

modtagdef fundus    'Calcified Drusen'           int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Peripheral Drusen'          int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Peripap Atrophy'            int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Art Sheathing'              int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Cen Art Occlus'             int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Br Art Occlus'              int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Cen Vein Occlus'            int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Br Vein Occlus'             int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Hollen Plaque'              int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Ast Hyalosis'               int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Nevus'                      int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Chorioret Scar'             int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'SWR Tension'                int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'SWR Cello Reflex'           int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Mac Hole'                   int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Histoplasmosis'             int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Ret Detach'                 int8   "${admin}"   tag         tag        false      'Other Lesions +PT'
modtagdef fundus    'Large C/D'                  int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Thick Vit/Glial'            int8   "${admin}"   tag         tag        false      'Other Lesions'
modtagdef fundus    'Other (comments)'           int8   "${admin}"   tag         tag        false      'Other Lesions +PT'

modtagdef fundus    'Other Lesions Summary'      int8   "${admin}"   tag         tag        false      'no/yes'

modtagdef fundus    'Diabetic Retinopathy Level' int8   "${admin}"   tag         tag        false      'Diabetic Retinopathy Level'

tag "fundus brief tags" "_cfg_file list tags" tagname "Modality"
tag "fundus brief tags" "_cfg_file list tags" tagname "Lesions Summary"
tag "fundus brief tags" "_cfg_file list tags" tagname "Other Lesions Summary"
tag "fundus brief tags" "_cfg_file list tags" tagname "Diabetic Retinopathy Level"

tag "fundus brief tags" "_cfg_tag list tags" tagname "Modality"
tag "fundus brief tags" "_cfg_tag list tags" tagname "Lesions Summary"
tag "fundus brief tags" "_cfg_tag list tags" tagname "Other Lesions Summary"
tag "fundus brief tags" "_cfg_tag list tags" tagname "Diabetic Retinopathy Level"
