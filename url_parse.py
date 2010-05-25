import ply.yacc as yacc

from url_lex import make_lexer, tokens

# use ast module to build abstract syntax tree
import url_ast

################################################
# here's the grammar and ast production rules

start = 'start'

def p_start(p):
    """start : filelist
             | verslist
             | file
             | vfile
             | upload
             | uploadform
             | uploadnew
             | tagdef
             | tags
             | tagsresttag
             | query
"""
    p[0] = p[1]

def p_filelist(p):
    """filelist : slash string
                | slash string slash
                | slash string slash FILE
                | slash string slash FILE slash"""
    p[0] = url_ast.FileList(appname=p[2])

def p_verslist(p):
    """verslist : slash string slash HISTORY slash string
                | slash string slash HISTORY slash string slash"""
    p[0] = url_ast.FileHistory(appname=p[2], data_id=p[6])

def p_file(p):
    """file : slash string slash FILE slash string
            | slash string slash FILE slash string slash"""
    p[0] = url_ast.FileIdVersion(appname=p[2], data_id=p[6])

def p_vfile(p):
    """vfile : slash string slash FILE slash string slash string"""
    p[0] = url_ast.FileIdVersion(appname=p[2], data_id=p[6], vers_id=p[8])

def p_upload(p):
    """upload : slash string slash UPLOAD slash string
              | slash string slash UPLOAD slash string slash"""
    p[0] = url_ast.Upload(appname=p[2], data_id=p[6])

def p_upload_form(p):
    """uploadform : slash string slash UPLOAD '?' NAME '=' string"""
    p[0] = url_ast.Upload(appname=p[2], data_id=p[8])

def p_upload_new(p):
    """uploadnew : slash string slash UPLOAD
                 | slash string slash UPLOAD slash"""
    p[0] = url_ast.Upload(appname=p[2])

def p_tagdef_start(p):
    """tagdef : slash string slash TAGDEF
              | slash string slash TAGDEF slash"""
    p[0] = url_ast.Tagdef(appname=p[2])

def p_tags(p):
    """tags : slash string slash TAGS slash string 
            | slash string slash TAGS slash string slash"""
    p[0] = url_ast.Tags(appname=p[2], data_id=p[6])

def p_tagsresttag(p):
    """tagsresttag : slash string slash TAGS slash string slash string 
            | slash string slash TAGS slash string slash string slash"""
    p[0] = url_ast.FileTags(appname=p[2], data_id=p[6], tag_id=p[8])

def p_query1(p):
    """query : slash string slash QUERY
             | slash string slash QUERY slash"""
    p[0] = url_ast.Query(appname=p[2], tagnames=[], queryopts={})

def p_query2a(p):
    """query : slash string slash QUERY queryopts"""
    p[0] = url_ast.Query(appname=p[2], tagnames=[], queryopts=p[5])

def p_query2b(p):
    """query : slash string slash QUERY slash queryopts"""
    p[0] = url_ast.Query(appname=p[2], tagnames=[], queryopts=p[6])

def p_query3(p):
    """query : slash string slash QUERY slash taglist"""
    p[0] = url_ast.Query(appname=p[2], tagnames=p[6], queryopts={})

def p_query4(p):
    """query : slash string slash QUERY slash taglist queryopts"""
    p[0] = url_ast.Query(appname=p[2], tagnames=p[6], queryopts=p[7])

def p_taglist(p):
    """taglist : string"""
    p[0] = [ p[1] ]

def p_taglist_grow(p):
    """taglist : taglist ';' string"""
    p[0] = p[1]
    p[0].append(p[3])

def p_queryopts(p):
    """queryopts : '?' string '=' string"""
    p[0] = { p[2] : p[4] }

def p_queryopts_grow(p):
    """queryopts : queryopts '&' string '=' string
                 | queryopts ';' string '=' string"""
    p[0] = p[1]
    p[0][p[3]] = p[5]

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
              | UPLOAD
              | HISTORY
              | STRING"""
    p[0] = p[1]

def p_stringplus(p):
    """string : STRING '+' STRING"""
    p[0] = p[1] + ' ' + p[3]
    

################################################
# provide wrappers to get a parser instance

def make_parser():
    # use this to shut it up: errorlog=yacc.NullLogger()
    return yacc.yacc(debug=False, errorlog=yacc.NullLogger())

def make_parse():
    parser = make_parser()
    lexer = make_lexer()
    def parse(s):
        return parser.parse(s, lexer=lexer)
    return parse

