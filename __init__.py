#!/usr/bin/env python
"""tagfiler: makes service of a tag catalog"""

from __future__ import generators

__version__ = "1.0"
__author__ = ["misd@isi.edu"]
__license__ = "University of Southern California"

import dataserv_app
import rest_fileio
import url_ast
import url_lex
import url_parse

url_parse_func = url_parse.make_parse()

