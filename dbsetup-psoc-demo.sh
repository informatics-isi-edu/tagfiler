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


#tagdef      TAGNAME               TYPE        OWNER      READPOL     WRITEPOL     MULTIVAL   TYPESTR    PKEY     TAGREF

#typedef       TYPENAME     DBTYPE        DESC                            TAGREF             ENUMs

## Types and Tags for PSOC  demo...

echo =====================BEGIN PSOC DEMO SETUP================================

demotypedef()
{
    local typename="$1"
    local dbtype="$2"
    local desc="$3"
    shift 3
    typedef "$typename" "$dbtype" "$desc" "" "$@"
}

demotypedef "mouse strain" text "Mouse strain"   "C57b6 C57 black 6" "nude nude" "skid skid" "other other strain"
demotypedef "sample type"  text "Sample type"    "serum serum" "tumor tumor"  "spleen spleen" "other other sample"
demotypedef "cancer type"  text "Cancer type"    "lymphoma lymphoma" "prostate prostate" "breast breast" "naive naive"
demotypedef "weight"       int8 "Weight (g)"
demotypedef "drug"         text "Drug"
demotypedef "dose"         int8 "Dose (mg/kg)"
demotypedef "dose period"  float8 "Repeat dose period (hours)"
demotypedef "serum sample type" text "Serum sample type" "termbleed terminal bleed" "other other"

demotagdef()
{
    tagdef "$1" "$2" "$admin" subject subject "$3" "$4" "$5" "$6"
}

demotagdef "address" text true "" false
demotagdef "email"   text true "" false
demotagdef dob       date false "" false
demotagdef dos       date false "" false
demotagdef start     date false "" false
demotagdef litter    int8 false "" false
demotagdef cage      int8 false "" false
demotagdef "start age"    int8 false "" false
demotagdef "mouse strain" text false "mouse strain" false
demotagdef "cancer type"  text false "cancer type" false
demotagdef "#cells"  float8 false "" false
demotagdef weight    int8 false "weight" false
demotagdef drug      text false "drug" false
demotagdef dose      int8 false "dose" false
demotagdef "lot#"    int8 false "" false
demotagdef "sample type" text false "sample type" false
demotagdef "serum sample type" text false "serum sample type" false
demotagdef freezer   int8 false "" false
demotagdef shelf     int8 false "" false

# all ID and ref types are assumed text for this demo

entity()
{
    # entity <idtag>
    tagdef  "$1" text "$admin" subject subject false "" true ""
    typedef "$1" text "$1 reference" "$1"
}


entityref1()
{
    # entityref1 <idtag> [<reftag>]...
    local idtag="$1"
    shift
    while [[ $# -gt 0 ]]
    do
      tagdef "$1" text "$admin" subject subject false "$idtag" false "$idtag"
      shift
    done
}

entityrefN()
{
    # entityrefN <idtag> [<reftag>]...
    local idtag="$1"
    shift
    while [[ $# -gt 0 ]]
    do
      tagdef "$1" text "$admin" subject subject true "$idtag" false "$idtag"
      shift
    done
}


entity     "mouseID"
entityref1 "mouseID" "mouse"
entityrefN "mouseID" "mice"

entity     "experimentID"
entityref1 "experimentID" "experiment"
entityrefN "experimentID" "experiments"

entity     "treatmentID"
entityref1 "treatmentID" "treatment"

entity     "observationID"
entityrefN "observationID" "observations"

entity     "sampleID"
entityrefN "sampleID" "samples"

entity     "researcherID"
entityref1 "researcherID" "researcher" "principal" "performer"
entityrefN "researcherID" "researchers"

entity     "labID"
entityref1 "labID" "lab"
entityrefN "labID" "labs"

entity     "siteID"
entityref1 "siteID" "site"
entityrefN "siteID" "sites"

entity     "supplierID"
entityref1 "supplierID" "supplier"
entityrefN "supplierID" "suppliers"

view()
{
    view=$(dataset "$1" view "$admin" "*")
    shift
    for tagname in "$@"
    do
      tag "$view" "_cfg_file list tags" tagdef "$1"
      tag "$view" "_cfg_tag list tags" tagdef "$1"
      shift
    done
}

view mouseID mouseID dob dos litter cage "start age" "mouse strain" "lot#" supplier treatment samples observations "cancer type" start performer "#cells" weight
view experimentID experimentID principal lab start mice observations
view treatmentID treatmentID drug dose "lot#" performer
view observationID observationID start weight performer samples
view sampleID sampleID start performer freezer shelf "sample type" "serum sample type" observations
view researcherID researcherID email lab
view labID labID site
view siteID siteID address
view supplierID supplierID address email

# some demo data

CSHL=$(dataset "" blank "$admin" "PSOC")
tag "$CSHL" siteID text "CSHL"
tag "$CSHL" address text "CSHL, 1 Bungtown Rd, Cold Spring Harbor, NY, 11724"

stanford=$(dataset "" blank "$admin" "PSOC")
tag "$stanford" siteID text "Stanford University"

lab1=$(dataset "" blank "$admin" "PSOC")
tag "$lab1" labID text "Scott Lowe"
tag "$lab1" site text "CSHL"

lab2=$(dataset "" blank "$admin" "PSOC")
tag "$lab2" labID text "Parag Mallick"
tag "$lab2" site text "Stanford University"

miething=$(dataset "" blank "miething" "PSOC")
tag "$miething" researcherID text "miething"
tag "$miething" email text "miething@cshl.edu"
tag "$miething" lab text "Scott Lowe"

parag=$(dataset "" blank "paragm" "PSOC")
tag "$parag" researcherID text "paragm"
tag "$parag" email text "paragm@stanford.edu"
tag "$parag" lab text "Parag Mallick"

CRL=$(dataset "" blank "$admin" "PSOC")
tag "$CRL" supplierID text "Charles River Laboratories"

experimentID=(miething-1 miething-2)
experimentStart=(2011-4-4 2011-4-11)
experimentMouseDob=(2011-3-2 2011-2-25)
experimentMouseDos=(2011-4-18 2011-4-25)
experimentLitter=(21 19)
experimentCage=(936 928)
experimentShelf=(12 8)

datediff()
{
    psql -t -A -q -c "select '$1'::date - '$2'::date"
}

for expnum in ${!experimentID[*]}
do
  exp=$(dataset "" blank "$admin" "PSOC")
  tag "$exp" experimentID text "${experimentID[$expnum]}"
  tag "$exp" principal text "miething"
  tag "$exp" lab text "Scott Lowe"
  tag "$exp" start date "${experimentStart[$expnum]}"

  for mousenum in {1..8}
  do
    mouse=$(dataset "" blank "$admin" "PSOC")
    mouseID="${experimentID[$expnum]}-$mousenum"
    tag "$mouse" mouseID text "$mouseID"
    tag "$exp" mice text "$mouseID"
    tag "$mouse" dob date "${experimentMouseDob[$expnum]}"
    tag "$mouse" dos date "${experimentMouseDos[$expnum]}"
    tag "$mouse" litter int8 "${experimentLitter[$expnum]}"
    tag "$mouse" cage int8 "${experimentCage[$expnum]}"
    tag "$mouse" "start age" int8 "$(datediff ${experimentStart[$expnum]} ${experimentMouseDob[$expnum]})"
    tag "$mouse" "mouse strain" text "C57b6"
    tag "$mouse" supplier text "Charles River Laboratories"
    tag "$mouse" "lot#" int8 67889
    tag "$mouse" "cancer type" text "lymphoma"
    tag "$mouse" start date "${experimentStart[$expnum]}"
    tag "$mouse" performer text "miething"
    tag "$mouse" "#cells" float8 "5e6"
    tag "$mouse" weight int8 $(( 98 + $RANDOM % 5 ))

    treat=$(dataset "" blank "$admin" "PSOC")
    treatID="${mouseID}"
    tag "$treat" treatmentID text "$treatID"
    tag "$mouse" treatment text "$treatID"
    if [[ $mousenum -lt 5 ]]
    then
	tag "$treat" drug text "cyclophosphamide"
	tag "$treat" dose int8 10
	tag "$treat" "lot#" int8 12345
    else
	tag "$treat" drug text "N/A"
    fi

    samp=$(dataset "" blank "$admin" "PSOC")
    sampID="${mouseID}-serum-1"
    tag "$samp" sampleID text "$sampID"
    tag "$mouse" samples text "$sampID"
    tag "$samp" start date "${experimentMouseDos[$expnum]}"
    tag "$samp" "sample type" text serum
    tag "$samp" "serum sample type" text "termbleed"
    tag "$samp" performer text "miething"
    tag "$samp" freezer int8 6
    tag "$samp" shelf int8 ${experimentShelf[$expnum]}

    obsv=$(dataset "" blank "$admin" "PSOC")
    obsvID="${mouseID}-A"
    tag "$obsv" observationID text "$obsvID"
    tag "$samp" observations text "$obsvID"
    tag "$obsv" samples text "$sampID"
    tag "$obsv" performer text "paragm"

  done

done

# some stored queries

psocfilename=${admin}-psoctemplate
psocdataset="name=DEMO%3A%20Create%20PSOC%20entries"
psoctemplate=$(dataset "DEMO: Create PSOC entries" file "${homepath}/file/${psocdataset}" "${admin}" "PSOC")
tag "${psoctemplate}" "template mode" text "embedded"
tag "${psoctemplate}" "file" text "${psocdataset}/${psocfilename}"

homelinks=(
$(dataset "DEMO: All experiments"               url "${homepath}/tags/experimentID?view=experimentID" "${admin}" "PSOC")
$(dataset "DEMO: Experiment miething-2"    url "${homepath}/file/experimentID=miething-2" "${admin}" "PSOC")
$(dataset "DEMO: All mice"                      url "${homepath}/tags/mouseID?view=mouseID" "${admin}" "PSOC")
$(dataset "DEMO: Mice in experiment miething-2" url "${homepath}/tags/experimentID=miething-1(mice)/?view=mouseID" "${admin}" "PSOC")
$(dataset "DEMO: Mice in experiment miething-2 which were treated w/ 10 mg/kg cyclophosphamide" url "${homepath}/tags/experimentID=miething-1(mice)/treatment=@(drug=cyclophosphamide;dose=10)?view=mouseID" "${admin}" "PSOC")
$(dataset "DEMO: Samples for mice in experiment miething-2" url "${homepath}/tags/experimentID=miething-1(mice)/(samples)/?view=sampleID" "${admin}" "PSOC")
$(dataset "DEMO: Samples for mice in experiment miething-2 which were treated w/ 10 mg/kg cyclophosphamide" url "${homepath}/tags/experimentID=miething-1(mice)/treatment=@(drug=cyclophosphamide;dose=10)(samples)/?view=sampleID" "${admin}" "PSOC")
$(dataset "DEMO: Observations for mice in experiment miething-2" url "${homepath}/tags/experimentID=miething-1(mice)/(samples)/(observations)/?view=observationID" "${admin}" "PSOC")
$(dataset "DEMO: Samples for mouse miething-2-2" url "${homepath}/tags/mouseID=miething-2-2(samples)/?view=sampleID" "${admin}" "PSOC")
${psoctemplate}
)

i=0
while [[ $i -lt "${#homelinks[*]}" ]]
do
   tag "${homelinks[$i]}" "list on homepage"
   tag "${homelinks[$i]}" "homepage order" int8 "$(( $i + 10 ))"
   i=$(( $i + 1 ))
done
