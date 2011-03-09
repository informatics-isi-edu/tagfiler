

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

################################################
# here's the grammar and ast production rules

start = 'start'

def p_start(p):
    """start : filelist
             | file
             | tagdef
             | tags
             | query
             | transmitnumber
             | study
             | appleterror
             | loglist
             | log
             | contact
"""
    p[0] = p[1]

def p_filelist(p):
    """filelist : slash string
                | slash string slash
                | slash string slash FILE
                | slash string slash FILE slash"""
    p[0] = url_ast.FileList(appname=p[2])
    
def p_filelist_opts1(p):
    """filelist : slash string queryopts"""
    p[0] = url_ast.FileList(appname=p[2], queryopts=p[3])
    
def p_loglist(p):
    """loglist : slash string slash LOG
               | slash string slash LOG slash"""
    p[0] = url_ast.LogList(appname=p[2])

def p_contact(p):
    """contact : slash string slash CONTACT"""
    p[0] = url_ast.Contact(appname=p[2])
    
def p_filelist_opts2(p):
    """filelist : slash string slash FILE queryopts"""
    p[0] = url_ast.FileList(appname=p[2], queryopts=p[5])

def p_file(p):
    """file : slash string slash FILE slash predlist_nonempty"""
    p[0] = url_ast.FileId(appname=p[2], subjpreds=p[6])

def p_log(p):
    """log : slash string slash LOG slash string"""
    p[0] = url_ast.LogId(appname=p[2], name=p[6])

def p_log_opts(p):
    """log : slash string slash LOG slash string queryopts"""
    p[0] = url_ast.LogId(appname=p[2], name=p[6], queryopts=p[7])

def p_file_opts(p):
    """file : slash string slash FILE slash predlist_nonempty queryopts"""
    p[0] = url_ast.FileId(appname=p[2], subjpreds=p[6], queryopts=p[7])

def p_tagdef(p):
    """tagdef : slash string slash TAGDEF
              | slash string slash TAGDEF slash"""
    # GET all definitions and a creation form (HTML)
    p[0] = url_ast.Tagdef(appname=p[2])

def p_tagdef_rest_get(p):
    """tagdef : slash string slash TAGDEF slash string"""
    # GET a single definition (URL encoded)
    p[0] = url_ast.Tagdef(appname=p[2], tag_id=p[6])

def p_tagdef_rest_put(p):
    """tagdef : slash string slash TAGDEF slash string queryopts"""
    # PUT queryopts supports typestr=string&multivalue=boolean&readpolicy=pol&writepolicy=pol
    #  where pol is in [ anonymous, users, file, fowner, tag, system ]
    p[0] = url_ast.Tagdef(appname=p[2], tag_id=p[6], queryopts=p[7])

def p_tags_all(p):
    """tags : slash string slash TAGS
            | slash string slash TAGS slash"""
    p[0] = url_ast.FileTags(appname=p[2])

def p_tags_all_opts(p):
    """tags : slash string slash TAGS queryopts"""
    p[0] = url_ast.FileTags(appname=p[2], queryopts=p[5])

def p_tags_all_slash_opts(p):
    """tags : slash string slash TAGS slash queryopts"""
    p[0] = url_ast.FileTags(appname=p[2], queryopts=p[6])

def p_tags(p):
    """tags : slash string slash TAGS slash predlist_nonempty 
            | slash string slash TAGS slash predlist_nonempty slash"""
    p[0] = url_ast.FileTags(appname=p[2], subjpreds=p[6])

def p_tags_opts(p):
    """tags : slash string slash TAGS slash predlist_nonempty queryopts"""
    p[0] = url_ast.FileTags(appname=p[2], subjpreds=p[6], queryopts=p[7])

def p_tagsvalrest(p):
    """tags : slash string slash TAGS slash predlist_nonempty slash tagvals"""
    p[0] = url_ast.FileTags(appname=p[2], subjpreds=p[6], tagvals=p[8])

def p_tagsvalrest_opts(p):
    """tags : slash string slash TAGS slash predlist_nonempty slash tagvals queryopts"""
    p[0] = url_ast.FileTags(appname=p[2], subjpreds=p[6], tagvals=p[8], queryopts=p[9])

def p_tagvals(p):
    """tagvals : tagval"""
    p[0] = dict()
    tag = p[1][0]
    vallist = p[1][1]
    p[0][tag] = list(vallist)

def p_tagvallist_grow(p):
    """tagvals : tagvals ';' tagval"""
    p[0] = p[1]
    tag = p[3][0]
    vallist = p[3][1]
    try:
        vals = p[0][tag]
        for val in vallist:
            vals.append(val)
    except:
        p[0][tag] = list(vallist)

def p_tagval(p):
    """tagval : string '=' vallist"""
    p[0] = ( p[1], p[3] )

def p_tag(p):
    """tagval : string"""
    p[0] = ( p[1], list() )

def p_query1(p):
    """query : slash string slash QUERY
             | slash string slash QUERY slash"""
    p[0] = url_ast.Query(appname=p[2], path=[([], [], [])], queryopts=web.storage())

def p_query2a(p):
    """query : slash string slash QUERY queryopts"""
    p[0] = url_ast.Query(appname=p[2], path=[([], [], [])], queryopts=p[5])

def p_query2b(p):
    """query : slash string slash QUERY slash queryopts"""
    p[0] = url_ast.Query(appname=p[2], path=[([], [], [])], queryopts=p[6])

def p_query3(p):
    """query : slash string slash QUERY slash querypath"""
    p[0] = url_ast.Query(appname=p[2], path=p[6], queryopts=web.storage())

def p_query4(p):
    """query : slash string slash QUERY slash querypath queryopts"""
    p[0] = url_ast.Query(appname=p[2], path=p[6], queryopts=p[7])

def p_querypath_general(p):
    """querypath_elem : predlist listtags_nonepsilon ordertags"""
    p[0] = ( p[1], p[2], p[3] )

def p_querypath_nopred(p):
    """querypath_elem : listtags_nonepsilon ordertags"""
    p[0] = ( [], p[1], p[2] )

def p_querypath_noorder(p):
    """querypath_elem : predlist listtags"""
    p[0] = ( p[1], p[2], [] )

def p_querypath_listonly(p):
    """querypath_elem : listtags"""
    p[0] = ( [], p[1], [] )

def p_querypath_base(p):
    """querypath : querypath_elem"""
    p[0] = [ p[1] ]

def p_querypath_extend(p):
    """querypath : querypath slash querypath_elem"""
    p[0] = p[1]
    ppreds, plisttags, pordertags = p[0][-1]
    if len(plisttags) == 0:
        # the parent path element has no listtags, default to 'vcontains'
        p[0][-1] = ( ppreds, [ 'vcontains' ], pordertags )
    p[0].append( p[3] )

def p_listtags(p):
    """listtags : listtags_epsilon
                | listtags_empty
                | listtags_nonempty"""
    p[0] = p[1]

def p_listtags_nonepsilon(p):
    """listtags_nonepsilon : listtags_empty
                           | listtags_nonempty"""
    p[0] = p[1]

def p_listtags_epsilon(p):
    """listtags_epsilon : """
    p[0] = []

def p_listtags_empty(p):
    """listtags_empty : '(' ')'"""
    p[0] = []

def p_listtags_nonempty(p):
    """listtags_nonempty : '(' vallist ')'"""
    p[0] = p[2]

def p_ordertags_empty(p):
    """ordertags : """
    p[0] = []

def p_ordertags_nonempty(p):
    """ordertags : vallist"""
    p[0] = p[1]

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

def p_pred_tag(p):
    """pred : string"""
    p[0] = web.Storage([ ('tag', p[1]), ('op', None), ('vals', []) ])

def p_pred_not_tag(p):
    """pred : string ':' NOT ':'"""
    p[0] = web.Storage([ ('tag', p[1]), ('op', ':not:'), ('vals', []) ])

def p_pred_vallist(p):
    """vallist : string"""
    p[0] = list([ p[1] ])

def p_pred_vallist_grow(p):
    """vallist : vallist ',' string"""
    p[0] = p[1]
    p[1].append(p[3])

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

def p_stringset(p):
    """stringset : string ',' string"""
    p[0] = set([p[1], p[3]])

def p_stringset_grow(p):
    """stringset : stringset ',' string"""
    p[0] = p[1]
    p[1].add(p[3])

def p_queryopts(p):
    """queryopts : '?' string '=' string"""
    p[0] = web.storage([(p[2], p[4])])

def p_queryopts_set(p):
    """queryopts : '?' string '=' stringset"""
    p[0] = web.storage([(p[2], p[4])])

def p_queryopts_short(p):
    """queryopts : '?' string
                 | '?' string '='"""
    p[0] = web.storage([(p[2], None)])

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
            p[0][p[3]] = v
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

def p_transmit_number(p):
    """transmitnumber : slash string slash TRANSMITNUMBER """
    p[0] = url_ast.TransmitNumber(appname=p[2])

def p_study(p):
    """study : slash string slash STUDY"""
    p[0] = url_ast.Study(appname=p[2])

def p_study_num(p):
    """study : slash string slash STUDY slash filename"""
    p[0] = url_ast.Study(appname=p[2], name=p[6])

def p_study_num_opts(p):
    """study : slash string slash STUDY slash filename queryopts"""
    p[0] = url_ast.Study(appname=p[2], name=p[6], queryopts=p[7])

def p_study_opts(p):
    """study : slash string slash STUDY queryopts"""
    p[0] = url_ast.Study(appname=p[2], queryopts=p[5])

def p_appleterror(p):
    """appleterror : slash string slash APPLETERROR"""
    p[0] = url_ast.AppletError(appname=p[2])

def p_appleterror_opts(p):
    """appleterror : slash string slash APPLETERROR queryopts"""
    p[0] = url_ast.AppletError(appname=p[2], queryopts=p[5])

# treat any sequence of '/'+ as a path divider
def p_slash(p):
    """slash : '/'
             | slash '/'"""
    pass

def p_filename(p):
    """filename : string"""
    p[0] = web.storage(name=p[1], version=None)

def p_filename_version(p):
    """filename : string '@' string"""
    try:
        x = int(p[3])
    except:
        raise ParseError(p[3], 'Filename part of URL has invalid version number:')
    p[0] = web.storage(name=p[1], version=p[3])

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

p_stringany.__doc__ =  "string : " + " \n| ".join(keywords.values()) + ' \n| STRING \n| spacestring'

def p_string_concat(p):
    """string : string string"""
    p[0] = p[1] + p[2]

class ParseError:
    """Exception for parse errors"""

    def __init__(self, t, message='URL parse error at token:'):
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
    return yacc.yacc(debug=False, optimize=0, tabmodule='urlparsetab', write_tables=0)
#    return yacc.yacc()

def make_parse():
    parser = make_parser()
    lexer = make_lexer()
    lock = threading.Lock()
    def parse(s):
        lock.acquire()
        try:
            return parser.parse(s, lexer=lexer)
        finally:
            lock.release()
    return parse

