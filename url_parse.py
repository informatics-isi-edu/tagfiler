import ply.yacc as yacc

from url_lex import make_lexer, tokens

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
"""
    p[0] = p[1]

def p_filelist(p):
    """filelist : slash string
                | slash string slash
                | slash string slash FILE
                | slash string slash FILE slash
                | slash string slash FILE queryopts"""
    # ignore queryopts
    p[0] = url_ast.FileList(appname=p[2])

def p_file(p):
    """file : slash string slash FILE slash string
            | slash string slash FILE slash string slash"""
    p[0] = url_ast.FileId(appname=p[2], data_id=p[6])

def p_file_opts(p):
    """file : slash string slash FILE slash string queryopts"""
    p[0] = url_ast.FileId(appname=p[2], data_id=p[6], queryopts=p[7])

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
    # PUT queryopts supports typestr=string&restricted=true/false&multivalue=true/false
    p[0] = url_ast.Tagdef(appname=p[2], tag_id=p[6], queryopts=p[7])

def p_tags(p):
    """tags : slash string slash TAGS slash string 
            | slash string slash TAGS slash string slash"""
    p[0] = url_ast.FileTags(appname=p[2], data_id=p[6])

def p_tagsrest(p):
    """tags : slash string slash TAGS slash string slash string 
            | slash string slash TAGS slash string slash string slash"""
    p[0] = url_ast.FileTags(appname=p[2], data_id=p[6], tag_id=p[8])

def p_tagsvalrest(p):
    """tags : slash string slash TAGS slash string slash string '=' string"""
    p[0] = url_ast.FileTags(appname=p[2], data_id=p[6], tag_id=p[8], value=p[10])

def p_query1(p):
    """query : slash string slash QUERY
             | slash string slash QUERY slash"""
    p[0] = url_ast.Query(appname=p[2], predlist=[], queryopts={})

def p_query2a(p):
    """query : slash string slash QUERY queryopts"""
    p[0] = url_ast.Query(appname=p[2], predlist=[], queryopts=p[5])

def p_query2b(p):
    """query : slash string slash QUERY slash queryopts"""
    p[0] = url_ast.Query(appname=p[2], predlist=[], queryopts=p[6])

def p_query3(p):
    """query : slash string slash QUERY slash predlist"""
    p[0] = url_ast.Query(appname=p[2], predlist=p[6], queryopts={})

def p_query4(p):
    """query : slash string slash QUERY slash predlist queryopts"""
    p[0] = url_ast.Query(appname=p[2], predlist=p[6], queryopts=p[7])

def p_predlist(p):
    """predlist : pred"""
    p[0] = [ p[1] ]

def p_predlist_grow(p):
    """predlist : predlist ';' pred"""
    p[0] = p[1]
    p[0].append(p[3])

def p_pred_tag_val_comp(p):
    """pred : string compare string"""
    p[0] = dict([ ('tag', p[1]), ('op', p[2]), ('val', p[3]) ])

def p_pred_tag(p):
    """pred : string"""
    p[0] = dict([ ('tag', p[1]), ('op', None), ('val', None) ])

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

def p_queryopts(p):
    """queryopts : '?' string '=' string"""
    p[0] = { p[2] : p[4] }

def p_queryopts_short(p):
    """queryopts : '?' string
                 | '?' string '='"""
    p[0] = { p[2] : None }

def p_queryopts_grow(p):
    """queryopts : queryopts '&' string '=' string
                 | queryopts ';' string '=' string"""
    p[0] = p[1]
    p[0][p[3]] = p[5]

def p_queryopts_grow_short(p):
    """queryopts : queryopts '&' string
                 | queryopts ';' string
                 | queryopts '&' string '='
                 | queryopts ';' string '='"""
    p[0] = p[1]
    p[0][p[3]] = None

# treat any sequence of '/'+ as a path divider
def p_slash(p):
    """slash : '/'
             | slash '/'"""
    pass

# grammatically, keywords can also be valid string values...
def p_stringany(p):
    """string : FILE
              | TAGS
              | TAGDEF
              | QUERY
              | STRING
              | LT
              | LEQ
              | GT
              | GEQ
              | LIKE
              | SIMTO
              | REGEXP
              | CIREGEXP"""
    p[0] = p[1]

def p_stringplus(p):
    """string : string '+' string"""
    p[0] = p[1] + ' ' + p[3]

def p_stringplus_concat(p):
    """string : string string"""
    p[0] = p[1] + p[2]

class ParseError:
    """Exception for parse errors"""

    def __init__(self):
        pass

def p_error(t):
    raise ParseError()



################################################
# provide wrappers to get a parser instance

def make_parser():
    # use this to shut it up: errorlog=yacc.NullLogger()
    # NullLogger attribute not supported by Python 2.4
    # return yacc.yacc(debug=False, errorlog=yacc.NullLogger())
    return yacc.yacc(debug=False)
#    return yacc.yacc()

def make_parse():
    parser = make_parser()
    lexer = make_lexer()
    def parse(s):
        return parser.parse(s, lexer=lexer)
    return parse

