
# this is a URL lexer tokenizing on _unescaped_ RFC 3986 reserved chars
# except '%' and strings of everything else including percent-encoded
# escape sequences, automatically url-decoding each string payload before
# matching for keywords and doing all other parsing

import urllib
import ply.lex as lex

# except '%' which we do not want to recognize
# adding STRING which is everything else

# RFC 3986 reserved characters
literals = [ '(', ')', ':', ';', ',', '=', '@', '&', '$', 
             '/', '?', '#', '[', ']', '!', '*', '"', '\'',
             '+' ]

# special strings which are keywords
keywords = {
    'file' : 'FILE',
    'tagdef' : 'TAGDEF',
    'tags' : 'TAGS',
    'query' : 'QUERY',
    'lt' : 'LT',
    'leq' : 'LEQ',
    'gt'  : 'GT',
    'geq' : 'GEQ',
    'like' : 'LIKE',
    'simto' : 'SIMTO',
    'regexp' : 'REGEX'
}

tokens = [ 'STRING' ] + list(keywords.values())

# unreserved characters in RFC 3986
# plus PERCENT so we accept percent-encoded forms as string content
# (consuming code must unescape after parsing)
def t_STRING(t):
    r'[-%_.~A-Za-z0-9]+'
    t.value = urllib.unquote(t.value)
    t.type = keywords.get(t.value, 'STRING')
    return t

class LexicalError:
    """Exception for lexical errors"""

    def __init__(self):
        pass

def t_error(t):
    raise LexicalError()

def make_lexer():
    return lex.lex(debug=False)

