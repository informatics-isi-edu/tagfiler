

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
import ply.yacc as yacc
import threading
import web
import urllib

from url_lex import make_lexer, tokens, keywords

# use ast module to build abstract syntax tree
import url_ast

url_parse_func = None

################################################
# here's the grammar and ast production rules

start = 'start'

def p_start(p):
    """start : maintenance
             | file
             | subject
             | tagdef
             | tags
             | querypathroot
             | catalog
             | configure
"""
    p[0] = p[1]

def p_querypathroot(p):
    """querypathroot : querypath"""
    p[0] = url_ast.Subquery(path=p[1])

#TODO: merge Toplevel representation into Catalog
#def p_toplevel(p):
#    """toplevel : slash string slash CATALOG slash NUMSTRING 
#                | slash string slash CATALOG slash NUMSTRING  slash"""
#    p[0] = url_ast.Toplevel(parser=url_parse_func, appname=p[2], catalog_id=p[4])

def p_maintenance(p):
    """maintenance : slash string slash CATALOG slash NUMSTRING slash MAINTENANCE queryopts"""
    p[0] = url_ast.Maintenance(parser=url_parse_func, appname=p[2], catalog_id=p[6], queryopts=p[9])

#def p_toplevel_opts1(p):
#    """toplevel : slash string queryopts"""
#    p[0] = url_ast.Toplevel(parser=url_parse_func, appname=p[2], queryopts=p[3])

#def p_toplevel_opts2(p):
#    """toplevel : slash string slash CATALOG slash NUMSTRING slash queryopts"""
#    p[0] = url_ast.Toplevel(parser=url_parse_func, appname=p[2], queryopts=p[4])

def p_catalogs(p):
    """catalog : slash string slash CATALOG
               | slash string slash CATALOG slash"""
    p[0] = url_ast.Catalog(parser=url_parse_func, appname=p[2])

def p_catalogs_id(p):
    """catalog : slash string slash CATALOG slash NUMSTRING
               | slash string slash CATALOG slash NUMSTRING slash"""
    p[0] = url_ast.Catalog(parser=url_parse_func, appname=p[2], catalog_id=p[6])

def p_configure(p):
    """configure : slash string slash CATALOG slash NUMSTRING slash CONFIG
                 | slash string slash CATALOG slash NUMSTRING slash CONFIG slash"""
    p[0] = url_ast.CatalogConfig(parser=url_parse_func, appname=p[2], catalog_id=p[6])

def p_configure_property(p):
    """configure : slash string slash CATALOG slash NUMSTRING slash CONFIG slash STRING
                 | slash string slash CATALOG slash NUMSTRING slash CONFIG slash STRING slash"""
    p[0] = url_ast.CatalogConfig(parser=url_parse_func, appname=p[2], catalog_id=p[6], prop_name=p[10])

def p_configure_property_value(p):
    """configure : slash string slash CATALOG slash NUMSTRING slash CONFIG slash STRING slash STRING
                 | slash string slash CATALOG slash NUMSTRING slash CONFIG slash STRING slash STRING slash"""
    p[0] = url_ast.CatalogConfig(parser=url_parse_func, appname=p[2], catalog_id=p[6], prop_name=p[10], prop_val=p[12])
    
def p_subject0(p):
    """subject : slash string slash CATALOG slash NUMSTRING slash SUBJECT"""
    p[0] = url_ast.Subject(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=[])

def p_subject1(p):
    """subject : slash string slash CATALOG slash NUMSTRING slash SUBJECT slash querypath"""
    p[0] = url_ast.Subject(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=p[10])

def p_subject1_opts(p):
    """subject : slash string slash CATALOG slash NUMSTRING slash SUBJECT slash querypath queryopts"""
    p[0] = url_ast.Subject(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=p[10], queryopts=p[11])

def p_subject_opts(p):
    """subject : slash string slash CATALOG slash NUMSTRING slash SUBJECT queryopts"""
    p[0] = url_ast.Subject(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=[], queryopts=p[9])

def p_file(p):
    """file : slash string slash CATALOG slash NUMSTRING slash FILE slash querypath"""
    p[0] = url_ast.FileId(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=p[10])

def p_file_opts(p):
    """file : slash string slash CATALOG slash NUMSTRING slash FILE slash querypath queryopts"""
    p[0] = url_ast.FileId(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=p[10], queryopts=p[11])

def p_tagdef(p):
    """tagdef : slash string slash CATALOG slash NUMSTRING slash TAGDEF
              | slash string slash CATALOG slash NUMSTRING slash TAGDEF slash"""
    # GET all definitions and a creation form (HTML)
    p[0] = url_ast.Tagdef(parser=url_parse_func, appname=p[2], catalog_id=p[6])

def p_tagdef_rest_get(p):
    """tagdef : slash string slash CATALOG slash NUMSTRING slash TAGDEF slash string"""
    # GET a single definition (URL encoded)
    p[0] = url_ast.Tagdef(parser=url_parse_func, appname=p[2], catalog_id=p[6], tag_id=p[10])

def p_tagdef_rest_put(p):
    """tagdef : slash string slash CATALOG slash NUMSTRING slash TAGDEF slash string queryopts"""
    # PUT queryopts supports dbtype=string&multivalue=boolean&readpolicy=pol&writepolicy=pol
    p[0] = url_ast.Tagdef(parser=url_parse_func, appname=p[2], catalog_id=p[6], tag_id=p[10], queryopts=p[11])

def p_tags_all(p):
    """tags : slash string slash CATALOG slash NUMSTRING slash TAGS
            | slash string slash CATALOG slash NUMSTRING slash TAGS slash"""
    p[0] = url_ast.FileTags(parser=url_parse_func, appname=p[2], catalog_id=p[6])

def p_tags_all_opts(p):
    """tags : slash string slash CATALOG slash NUMSTRING slash TAGS queryopts"""
    p[0] = url_ast.FileTags(parser=url_parse_func, appname=p[2], catalog_id=p[6], queryopts=p[9])

def p_tags_all_slash_opts(p):
    """tags : slash string slash CATALOG slash NUMSTRING slash TAGS slash queryopts"""
    p[0] = url_ast.FileTags(parser=url_parse_func, appname=p[2], catalog_id=p[6], queryopts=p[10])

def p_tags(p):
    """tags : slash string slash CATALOG slash NUMSTRING slash TAGS slash querypath"""
    p[0] = url_ast.FileTags(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=p[10])

def p_tags_opts(p):
    """tags : slash string slash CATALOG slash NUMSTRING slash TAGS slash querypath queryopts"""
    p[0] = url_ast.FileTags(parser=url_parse_func, appname=p[2], catalog_id=p[6], path=p[10], queryopts=p[11])

def p_querypath_elem_general(p):
    """querypath_elem : predlist '(' predlist ')' ordertags"""
    p[0] = ( p[1], p[3], p[5] )

def p_querypath_elem_brief(p):
    """querypath_elem : predlist"""
    p[0] = ( p[1], [], [] )

def p_querypath_base(p):
    """querypath : querypath_elem"""
    p[0] = [ p[1] ]

def p_querypath_extend(p):
    """querypath : querypath slash querypath_elem"""
    p[0] = p[1]
    ppreds, plisttags, pordertags = p[0][-1]
    p[0].append( p[3] )

def p_ordertags_empty(p):
    """ordertags : """
    p[0] = []

def p_ordertags_one(p):
    """ordertags : ordertag"""
    p[0] = [ p[1] ]

def p_ordertags_grow(p):
    """ordertags : ordertags ',' ordertag"""
    p[0] = p[1]
    p[0].append(p[3])

def p_ordertag_default(p):
    """ordertag : val"""
    p[0] = ( p[1], None )

def p_ordertag_directional(p):
    """ordertag : val direction """
    p[0] = ( p[1], p[2] )

def p_direction(p):
    """direction : ':' ASC ':'
                 | ':' DESC ':' """
    p[0] = ':' + p[2].lower() + ':'

def p_predlist_empty(p):
    """predlist : """
    p[0] = []

def p_predlist_nonempty(p):
    """predlist : predlist_nonempty"""
    p[0] = p[1]

def p_predlist(p):
    """predlist_nonempty : pred"""
    p[0] = list([ p[1] ])

def p_predlist_grow(p):
    """predlist_nonempty : predlist_nonempty ';' pred"""
    p[0] = p[1]
    p[0].append(p[3])

def p_pred_tag_val_comp(p):
    """pred : string compare vallist"""
    p[0] = web.Storage([ ('tag', p[1]), ('op', p[2]), ('vals', p[3]) ])

def p_pred_tag_val_comp_epsilon(p):
    """pred : string compare"""
    p[0] = web.Storage([ ('tag', p[1]), ('op', p[2]), ('vals', ['']) ])

def p_pred_tag(p):
    """pred : string"""
    p[0] = web.Storage([ ('tag', p[1]), ('op', None), ('vals', []) ])

def p_pred_not_tag(p):
    """pred : string ':' ABSENT ':'"""
    p[0] = web.Storage([ ('tag', p[1]), ('op', ':absent:'), ('vals', []) ])

def p_pred_vallist(p):
    """vallist : val"""
    p[0] = list([ p[1] ])

def p_pred_vallist_grow(p):
    """vallist : vallist ',' val"""
    p[0] = p[1]
    p[1].append(p[3])

def p_pred_val_string(p):
    """val : string"""
    p[0] = p[1]

def p_pred_val_subquery(p):
    """val : '@' '(' querypath ')' """
    p[0] = url_ast.Subquery(path=p[3])

def p_compare_eq(p):
    """compare : '='"""
    p[0] = '='

def p_compare_neq(p):
    """compare : '!' '='"""
    p[0] = '!='

def p_compare_regex(p):
    """compare : ':' REGEXP ':'
               | ':' CIREGEXP ':'"""
    p[0] = ':' + p[2].lower() + ':'

def p_compare_nregex(p):
    """compare : ':' '!' REGEXP ':'
               | ':' '!' CIREGEXP ':'"""
    p[0] = ':!' + p[3].lower() + ':'

ineqmap = { 'lt' : ':lt:', 'leq' : ':leq:', 'gt' : ':gt:', 'geq' : ':geq:',
            'like' : ':like:', 'simto' : ':simto:'}

def p_compare_ineq(p):
    """compare : ':' LT ':'
               | ':' GT ':'
               | ':' LEQ ':'
               | ':' GEQ ':'
               | ':' LIKE ':'
               | ':' SIMTO ':'"""
    p[0] = ineqmap[ p[2].lower() ]

def p_compare_tsv(p):
    """compare : ':' WORD ':'"""
    p[0] = ':' + p[2].lower() + ':'

def p_compare_ntsv(p):
    """compare : ':' '!' WORD ':'"""
    p[0] = ':!' + p[3].lower() + ':'

def p_stringset(p):
    """stringset : string ',' string"""
    p[0] = set([p[1], p[3]])

def p_stringset_grow(p):
    """stringset : stringset ',' string"""
    p[0] = p[1]
    p[1].add(p[3])

def p_queryopts_empty(p):
    """queryopts : '?'"""
    p[0] = web.storage()

def p_queryopts_nonempty(p):
    """queryopts : '?' queryopts_base"""
    p[0] = p[2]

def p_queryopts(p):
    """queryopts_base : string '=' string
                      | string '=' stringset"""
    p[0] = web.storage([(p[1], p[3])])

def p_queryopts_short(p):
    """queryopts_base : string
                      | string '='"""
    p[0] = web.storage([(p[1], None)])

def p_queryopts_grow(p):
    """queryopts : queryopts '&' string '=' string
                 | queryopts ';' string '=' string"""
    p[0] = p[1]
    if p[0].has_key(p[3]):
        v = p[0][p[3]]
        if type(v) != set:
            v = set([ v ])
            p[0][p[3]] = v
        v.add(p[5])
    else:
        p[0][p[3]] = p[5]

def p_queryopts_grow_set(p):
    """queryopts : queryopts '&' string '=' stringset
                 | queryopts ';' string '=' stringset"""
    p[0] = p[1]
    if p[0].has_key(p[3]):
        v = p[0][p[3]]
        if type(v) != set:
            p[0][p[3]] = set([ v ])
        v.update(p[5])
    else:
        p[0][p[3]] = p[5]

def p_queryopts_grow_short(p):
    """queryopts : queryopts '&' string
                 | queryopts ';' string
                 | queryopts '&' string '='
                 | queryopts ';' string '='"""
    p[0] = p[1]
    if p[0].has_key(p[3]):
        v = p[0][p[3]]
        if type(v) != list:
            v = set([ v ])
            p[0][p[3]] = v
        v.add(None)
    else:
        p[0][p[3]] = None

# treat any sequence of '/'+ as a path divider
def p_slash(p):
    """slash : '/'
             | slash '/'"""
    pass

def p_spacestring(p):
    """spacestring : '+'"""
    p[0] = ' '

# grammatically, keywords can also be valid string values...
def p_stringany(p):
    """stub"""
    # weird bit:
    # this doc string is a grammar rule allowing all keywords to be used as string content
    # in contexts where strings are expected.  to avoid this list being inconsistent with
    # changes to the token set, we generate it automatically.
    # this will fail if __doc__ cannot be mutated before yacc reads it
    p[0] = p[1]

p_stringany.__doc__ =  "string : " + " \n| ".join(keywords.values()) + ' \n| ESCAPESTRING \n| STRING \n| NUMSTRING \n| spacestring'

def p_string_concat(p):
    """string : string string"""
    p[0] = p[1] + p[2]

class ParseError (RuntimeError):
    """Exception for parse errors"""

    def __init__(self, t, message='URL parse error at token:'):
        RuntimeError.__init__(self)
        web.debug(message, t)
        pass

def p_error(t):
    raise ParseError(t)



################################################
# provide wrappers to get a parser instance

def make_parser():
    # use this to shut it up: errorlog=yacc.NullLogger()
    # NullLogger attribute not supported by Python 2.4
    # return yacc.yacc(debug=False, errorlog=yacc.NullLogger())
    return yacc.yacc(debug=False, optimize=1, tabmodule='urlparsetab', write_tables=1)
#    return yacc.yacc()

def make_parse():
    lock = threading.Lock()
    lock.acquire()
    try:
        parser = make_parser()
        lexer = make_lexer()
    finally:
        lock.release()
        
    def parse(s):
        lock.acquire()
        try:
            return parser.parse(s, lexer=lexer)
        finally:
            lock.release()
    return parse

# provide a mutexed parser instance for all to use
url_parse_func = make_parse()

