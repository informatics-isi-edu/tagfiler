

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
             '/', '?', '#', '[', ']', '!', '"', '\'',
             '+' ]
# removed '*' because mozilla doesn't honor its reserved status

# special strings which are keywords
keywords = {
    'file' : 'FILE',
    'subject' : 'SUBJECT',
    'tagdef' : 'TAGDEF',
    'tags' : 'TAGS',
    'query' : 'QUERY',
    'lt' : 'LT',
    'leq' : 'LEQ',
    'gt'  : 'GT',
    'geq' : 'GEQ',
    'like' : 'LIKE',
    'simto' : 'SIMTO',
    'regexp' : 'REGEXP',
    'ciregexp' : 'CIREGEXP',
    'absent' : 'ABSENT',
    'transmitnumber' : 'TRANSMITNUMBER',
    'study' : 'STUDY',
    'appleterror' : 'APPLETERROR',
    'asc' : 'ASC',
    'desc' : 'DESC',
    'ui' : 'UI'
}

tokens = [ 'ESCAPESTRING', 'STRING', 'NUMSTRING' ] + list(keywords.values())

# unreserved characters in RFC 3986
# plus PERCENT so we accept percent-encoded forms as string content
# plus ASTERISK because mozilla doesn't quote it properly
# (consuming code must unescape after parsing)

def urlunquote(url):
    if type(url) not in [ str, unicode ]:
        url = str(url)
    text = urllib.unquote_plus(url)
    if type(text) == str:
        text = unicode(text, 'utf8')
    elif type(text) == unicode:
        pass
    else:
        raise RuntimeError('unexpected decode type %s in urllex.urlunquote()' % type(text))
    return text

def t_ESCAPESTRING(t):
    r'(%[0-9A-Fa-f][0-9A-Fa-f])+'
    t.value = urlunquote(t.value)
    return t

def t_NUMSTRING(t):
    r'[0-9]+'
    return t

def t_STRING(t):
    r'[-*_.~A-Za-z]+'
    t.type = keywords.get(t.value, 'STRING')
    return t

class LexicalError (RuntimeError):
    """Exception for lexical errors"""

    def __init__(self):
        RuntimeError.__init__(self)
        pass

def t_error(t):
    raise LexicalError()

def make_lexer():
    return lex.lex(debug=False, optimize=1, lextab='urllextab')

