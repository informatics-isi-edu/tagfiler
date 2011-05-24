#!/usr/bin/env python
"""tagfiler: makes service of a tag catalog"""
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

from __future__ import generators

__version__ = "1.0"
__author__ = ["misd@isi.edu"]
__license__ = "University of Southern California"

import dataserv_app
import subjects
import rest_fileio
import url_ast
import url_lex
import url_parse

