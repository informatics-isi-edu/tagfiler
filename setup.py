
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
# ...

from distutils.core import setup

setup(name="tagfiler",
      version="1.0",
      description="service of a tag catalog",
      package_dir={"tagfiler": "src/tagfiler"},
      packages=["tagfiler"],
      package_data={
        "tagfiler": ["templates/*"],
      },
      scripts=map(lambda x: "scripts/" + x,
                  ["tagfiler-webauthn2-deploy.py",
                   "tagfiler-webauthn2-manage.py"]),
      #requires=["web.py", "ply", "pytz", "psycopg2", "python-dateutil"],
      author="MISD",
      author_email="misd@isi.edu",
      url="https://confluence.misd.isi.edu:8443/display/PSOC/PSOC+Tagfiler+Data+Repository",
      long_description="For data sharing, tagfiler is using a data repository developed at the USC/ISI Medical Information Systems Division (MISD).",

      classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP",
        ],
     )
