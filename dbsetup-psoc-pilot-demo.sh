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
demotypedef "sample type"  text "Sample type"    "t0 t0" "t1 t1"  "t2 t2" "t3 t3" "t4 t4" "t5 t5" "t6 t6"
demotypedef "cancer type"  text "Cancer type"    "lymphoma lymphoma" "prostate prostate" "breast breast" "naive naive"
demotypedef "cell type"  text "Cell type"    "Arf-/- Arf-/-" "Arf-/-Luc+ Arf-/- Luc+" "Arf-/-Luc- Arf-/- Luc-" "control control" "p53-/- p53-/-"
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
demotagdef "comment"   text false "" false
demotagdef dob       date false "" false
demotagdef dos       date false "" false
demotagdef start     date false "" false
demotagdef litter    int8 false "" false
demotagdef cage      int8 false "" false
demotagdef "start age"    int8 false "" false
demotagdef "mouse strain" text false "mouse strain" false
demotagdef "mouse label"    int8 false "" false
demotagdef "cancer type"  text false "cancer type" false
demotagdef "#cells"  float8 false "" false
demotagdef "cell type"  text false "cell type" false
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

view mouseID mouseID "mouse label" cage start "mouse strain" dob "cell type" "#cells" dos treatment samples
view experimentID experimentID start mice
view treatmentID treatmentID drug dose start
view observationID observationID start comment
view sampleID sampleID start "sample type" observations
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

# some stored queries

psocfilename=${admin}-psoctemplate
psocdataset="name=DEMO%3A%20Create%20PSOC%20entries"
psoctemplate=$(dataset "DEMO: Create PSOC entries" file "${homepath}/file/${psocdataset}" "${admin}" "PSOC")
tag "${psoctemplate}" "template mode" text "embedded"
tag "${psoctemplate}" "file" text "${psocdataset}/${psocfilename}"

homelinks=(
${psoctemplate}
)

i=0
while [[ $i -lt "${#homelinks[*]}" ]]
do
   tag "${homelinks[$i]}" "list on homepage"
   tag "${homelinks[$i]}" "homepage order" int8 "$(( $i + 10 ))"
   i=$(( $i + 1 ))
done
