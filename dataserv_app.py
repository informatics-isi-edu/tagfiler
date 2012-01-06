
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
import re
import urllib
import web
import psycopg2
import os
import logging
import subprocess
import itertools
import socket
import datetime
import dateutil.parser
import dateutil.relativedelta
import pytz
import traceback
import distutils.sysconfig
import sys
import random
import time
import math
import string
from logging.handlers import SysLogHandler
import json
try:
    import webauthn
except:
    pass
import base64
import struct

# we interpret RFC 3986 reserved chars as metasyntax for dispatch and
# structural understanding of URLs, and all escaped or
# "percent-encoded" sequences as payload within that structure.
# clients MUST NOT percent-encode the metacharacters structuring the
# query, and MUST percent-encode those characters when they are meant
# to form parts of the payload strings.  the client MAY percent-encode
# other non-reserved characters but it is not necessary.
#
# we dispatch everything through parser and then dispatch on AST.
#
# see Application.__init__() and prepareDispatch() for real dispatch
# see rules = [ ... ] for real matching rules

render = None

def downcast_value(dbtype, value, range_extensions=False):
    
    if dbtype == 'boolean':
        if hasattr(value, 'lower'):
            if value.lower() in [ 'true', 'yes', 't', 'on' ]:
                return True
            elif value.lower() in [ 'false', 'no', 'f', 'off' ]:
                return False
        elif type(value) == bool:
            return value
        raise ValueError('Value %s of type %s cannot be coerced to boolean' % (str(value), type(value)))
    
    elif dbtype == 'text':
        value = '%s' % value
        
    elif dbtype in [ 'int8', 'float8', 'date', 'timestamptz', 'interval' ] and range_extensions and type(value) in [ str, unicode ]:
        m = re.match(' *[(](?P<lower>[^,()]+) *, *(?P<upper>[^,()]+)[)] *', value)

        if m:
            # compound syntax: ( lower, upper )
            lower = downcast_value(dbtype, m.group('lower'))
            upper = downcast_value(dbtype, m.group('upper'))
            return (lower, upper)
        
        elif value.count('+/-') == 1:
            # compound syntax:  center +/- delta
            parts = value.split('+/-')

            center = downcast_value(dbtype, parts[0].strip())

            if dbtype in [ 'date', 'timestamptz' ]:
                delta = downcast_value('interval', parts[1].strip(), range_extensions=False)
            else:
                delta = downcast_value(dbtype, parts[1].strip(), range_extensions=False)

            return (center - delta, center + delta)
        else:
            # treat it as a regular value
            return downcast_value(dbtype, value, range_extensions=False)
        
    elif dbtype == 'interval':
        # naively handle ISO 8601 period notation to initialize a time interval based on numbers of specific time units
        m = re.match('P *(?P<interval>[-.:0-9TYMWDHMS ]+)', value)
        if m:
            interval = m.group('interval')

            # check for ISO 8601 alternative notation yyyy-mm-ddThh:mm:ss
            m = re.match('(?P<years>[0-9]{4})-(?P<months>[0-9]{2})-(?P<days>[0-9]{2}) *T *(?P<hours>[0-9]{2}):(?P<minutes>[0-9]{2}):(?P<seconds>[0-9]{2}(.[0-9]+)?)',
                         interval)
            if m:
                g = dict([ (k, float(v)) for k, v in m.groupdict().items() if v != None ])
            else:
                # assume ISO 8601 period with designators notation yY mM dD T hH mM sS
                datepart = ''
                timepart = ''
                parts = interval.split('T')

                if len(parts) > 0:
                    datepart = parts[0]
                if len(parts) > 1:
                    timepart = parts[1]
                if len(parts) > 2:
                    raise ValueError('Value %s not a valid ISO 8601 time period with designators.' % value)

                g = dict([ (dict(Y='years', M='months', W='weeks', D='days')[k], float(v)) for v, k in re.findall('([.0-9]+) *([YMWD])', datepart) ])

                g.update(dict([ (dict(H='hours', M='minutes', S='seconds')[k], float(v)) for v, k in re.findall('([.0-9]+) *([HMS])', timepart) ]))

            if g.has_key('seconds'):
                g['microseconds'] = g['seconds'] * 1000000.0
                del g['seconds']

            g = dict([ (k, int(v)) for k, v in g.items() ])

            # TODO: convert this to timedelta so psycopg2 adaptation can convert it to interval?
            return dateutil.relativedelta.relativedelta(**g)
        else:
            raise ValueError('Value %s not a valid ISO 8601 time period.' % value)

    elif dbtype == 'int8':
        value = int(value)

    elif dbtype == 'float8':
        value = float(value)

    elif dbtype in [ 'date', 'timestamptz' ]:
        if value == 'now':
            value = datetime.datetime.now(pytz.timezone('UTC'))
        elif type(value) in [ str, unicode ]:
            value = dateutil.parser.parse(value)

    else:
        pass

    return value

def myunicode(v):
    if type(v) == list:
        return [ myunicode(elem) for elem in v ]
    if type(v) == str:
        return unicode(v, 'utf8')
    else:
        return v

def myutf8(v):
    if type(v) == unicode:
        return v.encode('utf8')
    else:
        return v
        
def db_dbquery(db, query, vars={}):
    """Query wrapper to handle UTF-8 encoding issues.
    
    PostgreSQL understands UTF-8, but web.db does not understand unicode.
    
    1. Convert unicode query strings and vars to UTF-8 encoded raw strings.
    
    2. Convert query results in UTF-8 back to unicode.
    """

    def myunicode_storage(v):
        return web.Storage( [ (myunicode(key), myunicode(value)) for (key, value) in v.items() ] )

    query = myutf8(query)
    vars = myunicode_storage(vars)

    results = db.query(query, vars=vars)

    def iterwrapper(iter):
        for r in iter:
            yield r

    if hasattr(results, '__iter__'):
        # try to map results over iterator
        length = len(results)
        results = web.iterbetter(iterwrapper(itertools.imap(myunicode_storage, results)))
        results.__len__ = lambda: length
        return results
    else:
        # assume it is not an iterable result
        return myunicode(results)
    
class Values:
    """Simple helper class to build up a set of values and return keys suitable for web.db.query."""
    def __init__(self):
        self.va = []

    def add(self, v, dbtype='text', range_extensions=False):
        i = len(self.va)
        v = downcast_value(dbtype, v, range_extensions=range_extensions)
        if type(v) == tuple and len(v) == 2:
            self.va.append(v[0])
            self.va.append(v[1])
            return ('v%d' % i, 'v%d' % (i+1))
        else:
            self.va.append(v)
            return 'v%d' % i

    def pack(self):
        return dict([ ('v%d' % i, self.va[i]) for i in range(0, len(self.va)) ])

class DbCache:
    """A little helper to share state between web requests."""

    def __init__(self, idtagname, idalias=None):
        self.idtagname = idtagname
        self.idalias = idalias
        self.cache = dict()
        self.fill_txid = None

    def select(self, db, fillfunc, idtagval=None):
        def latest_txid():
            # modified time is latest modification time of:
            #  identifying tag (tracked as "tag last modified txid" on its tagdef
            #  individual subjects (tracked as "subject last tagged txid" on each identified subject
            results = db_dbquery(db, 'SELECT max(txid) AS txid FROM ('
                              + 'SELECT max(value) AS txid FROM %s' % wraptag('subject last tagged txid')
                              + ' WHERE subject IN (SELECT subject FROM subjecttags WHERE tagname = $idtag)'
                              + ' UNION '
                              + 'SELECT value AS txid FROM %s' % wraptag('tag last modified txid')
                              + ' WHERE subject IN (SELECT subject FROM %s WHERE value = $idtag)) AS a' % wraptag('tagdef'),
                              vars=dict(idtag=self.idtagname))
            return results[0].txid

        latest = latest_txid()
        
        if self.fill_txid == None or latest > self.fill_txid:
            # need to refill cache
            if self.idalias:
                self.cache = dict( [ (res[self.idalias], res) for res in fillfunc() ] )
            else:
                self.cache = dict( [ (res[self.idtagname], res) for res in fillfunc() ] )
            self.fill_txid = latest

            #web.debug('DbCache: filled %s cache txid = %s' % (self.idtagname, self.fill_txid))
        else:
            pass
            #web.debug('DbCache: cache hit %s cache' % self.idtagname)
            
        if idtagval != None:
            return self.cache.get(idtagval, None)
        else:
            return self.cache.itervalues()

class PerUserDbCache:

    max_cache_seconds = 500
    purge_interval_seconds = 60

    def __init__(self, idtagname, idalias=None):
        self.idtagname = idtagname
        self.idalias = idalias
        self.caches = dict()
        self.last_purge_time = None

    def purge(self):
        now = datetime.datetime.now(pytz.timezone('UTC'))
        if self.last_purge_time and (now - self.last_purge_time).seconds < PerUserDbCache.purge_interval_seconds:
            pass
        else:
            self.last_purge_time = now
            for item in self.caches.items():
                key, entry = item
                ctime, cache = entry
                if (now - ctime).seconds > PerUserDbCache.max_cache_seconds:
                    self.caches.pop(key, None)

    def select(self, db, fillfunc, user, idtagval=None):
        ctime, cache = self.caches.get(user, (None, None))
        now = datetime.datetime.now(pytz.timezone('UTC'))
        if not ctime:
            cache = DbCache(self.idtagname, self.idalias)
        results = cache.select(db, fillfunc, idtagval)
        self.caches[user] = (now, cache)
        self.purge()
        return results

config_cache = PerUserDbCache('config')
tagdef_cache = PerUserDbCache('tagdef', 'tagname')
typedef_cache = PerUserDbCache('typedef')
view_cache = PerUserDbCache('view')

def wraptag(tagname, suffix='', prefix='_'):
    return '"' + prefix + tagname.replace('"','""') + suffix + '"'

""" Set the logger """
logger = logging.getLogger('tagfiler')

#filehandler = logging.FileHandler('/var/www/tagfiler-logs/messages')
#fileformatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
#filehandler.setFormatter(fileformatter)
#logger.addHandler(filehandler)

sysloghandler = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL1)
syslogformatter = logging.Formatter('%(name)s[%(process)d.%(thread)d]: %(message)s')
sysloghandler.setFormatter(syslogformatter)
logger.addHandler(sysloghandler)

logger.setLevel(logging.INFO)

if hasattr(json, 'write'):
    jsonWriter = json.write
    jsonReader = json.read
elif hasattr(json, 'dumps'):
    jsonWriter = json.dumps
    jsonReader = json.loads
else:
    raise RuntimeError(ast=None, data='Could not configure JSON library.')



def urlquote(url, safe=""):
    "define common URL quote mechanism for registry URL value embeddings"
    if type(url) not in [ str, unicode ]:
        url = str(url)

    if type(url) == unicode:
        url = url.encode('utf8')

    url = urllib.quote(url, safe=safe)
        
    if type(url) == str:
        url = unicode(url, 'utf8')
        
    return url

def urlunquote(url):
    if type(url) not in [ str, unicode ]:
        url = str(url)
        
    url = urllib.unquote_plus(url)
    
    if type(url) == str:
        url = unicode(url, 'utf8')

    return url

def parseBoolString(theString):
    if theString.lower() in [ 'true', 't', 'yes', 'y' ]:
        return True
    else:
        return False

def predlist_linearize(predlist, quotefunc=urlquote, sort=True):
    def pred_linearize(pred):
        vals = [ myunicode(quotefunc(val)) for val in pred.vals ]
        if sort:
            vals.sort()
        vals = u','.join(vals)
        if pred.op:
            return myunicode(quotefunc(pred.tag)) + myunicode(pred.op) + vals
        else:
            return myunicode(quotefunc(pred.tag))
    predlist = [ pred_linearize(pred) for pred in predlist ]
    if sort:
        predlist.sort()
    return u';'.join(predlist)

def path_linearize(path, quotefunc=urlquote):
    def elem_linearize(elem):
        linear = predlist_linearize(elem[0], quotefunc)
        if elem[1]:
            linear += u'(' + predlist_linearize(elem[1], quotefunc) + u')'
            if elem[2]:
                linear += u','.join([ u"%s%s" % (myunicode(quotefunc(otag)), {':asc:': u':asc:',
                                                                              ':desc:': u':desc:',
                                                                              None: ''}[dir])
                                      for otag, dir in elem[2] ])
        return linear
    return u'/' + u'/'.join([ elem_linearize(elem) for elem in path ])

def reduce_name_pred(x, y):
    names = set()
    if type(x) is web.Storage:
        if x.tag == 'name' and x.op == '=':
            for name in x.vals or []:
                names.add(name)
    if type(y) is web.Storage:
        if y.tag == 'name' and y.op == '=':
            for name in y.vals or []:
                names.add(name)
    if type(x) is not web.Storage and x:
        names.add(x)
    if type(y) is not web.Storage and y:
        names.add(y)
    if len(names) > 1:
        raise KeyError('too many names')
    elif len(names) == 1:
        return names.pop()
    else:
        return None
            
def make_filter(allowed):
    allchars = string.maketrans('', '')
    delchars = ''.join([c for c in allchars if c not in allowed])
    return lambda s, a=allchars, d=delchars: type(s) == str and s.translate(a,d) or type(s) == unicode and s.translate(dict([ (ord(c), None) for c in d])) or str(s).translate(a, d)

idquote = make_filter(string.letters + string.digits + '_-:.' )

def buildPolicyRules(rules, fatal=False):
    remap = dict()
    for rule in rules:
        srcrole, dstrole, readers, writers, readok, writeok = rule.split(';', 6)
        srcrole = urlunquote(srcrole.strip())
        dstrole = urlunquote(dstrole.strip())
        readers = readers.strip()
        writers = writers.strip()
        readok = readok.strip().lower() in [ 'true', 'yes' ]
        writeok = writeok.strip().lower() in [ 'true', 'yes' ]
        if remap.has_key(srcrole):
            web.debug('Policy rule "%s" duplicates already-mapped source role.' % rule)
            if fatal:
                raise KeyError()
            else:
                continue
        if readers != '':
            readers = [ urlunquote(reader.strip()) for reader in readers.split(',') ]
            readers = [ reader for reader in readers if reader != '' ]
        else:
            readers = []
        if writers != '':
            writers = [ urlunquote(writer.strip()) for writer in writers.split(',') ]
            writers = [ writer for writer in writers if writer != '' ]
        else:
            writers = []
        remap[srcrole] = (dstrole, readers, writers, readok, writeok)
    return remap

def traceInChunks(seq):
    length = 5000
    chunks = [seq[i:i+length] for i in range(0, len(seq), length)]
    for chunk in chunks:
        web.debug(chunk)


class WebException (web.HTTPError):
    def __init__(self, ast, status, data=u'', headers={}, desc=u'%s'):
        self.detail = urlquote(desc % data)
        #web.debug(self.detail, desc, data, desc % data)
        if ast and ast.start_time:
            now = datetime.datetime.now(pytz.timezone('UTC'))
            elapsed = '%d.%3.3d' % ( (now - ast.start_time).seconds, (now - ast.start_time).microseconds / 1000 )
            ast.last_log_time = now
        else:
            elapsed = '-.---'
        logger.info(myutf8(u'%ss %s%s req=%s -- %s' % (elapsed,
                                                       web.ctx.ip, ast and ast.authn and ast.authn.role and u' user=%s' % urllib.quote(ast.authn.role) or u'',
                                                       ast and ast.request_guid or u'', desc % data)))
        data = render.Error(status, desc, data)
        m = re.match('.*MSIE.*',
                     web.ctx.env.get('HTTP_USER_AGENT', 'unknown'))
        if m and False:
            status = '200 OK'
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class NotFound (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data=u'', headers={}):
        status = '404 Not Found'
        desc = u'The requested %s could not be found.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class Forbidden (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data=u'', headers={}):
        status = '403 Forbidden'
        desc = u'The requested %s is forbidden.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class Unauthorized (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data=u'', headers={}):
        status = '401 Unauthorized'
        desc = u'The requested %s requires authorization.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class BadRequest (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data=u'', headers={}):
        status = '400 Bad Request'
        desc = u'The request is malformed. %s'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class Conflict (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data=u'', headers={}):
        status = '409 Conflict'
        desc = u'The request conflicts with the state of the server. %s'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class IntegrityError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data=u'', headers={}):
        status = '500 Internal Server Error'
        desc = u'The request execution encountered a integrity error: %s.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class RuntimeError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data=u'', headers={}):
        status = '500 Internal Server Error'
        desc = u'The request execution encountered a runtime error: %s.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

try:
    # allow a per-daemon account set of configuration parameters to override hard-coded defaults
    homedir = os.environ.get('HOME', './')
    f = open('%s/tagfiler-config.json' % homedir)
    s = f.read()
    f.close()
    global_env = jsonReader(s)
except:
    global_env = {}

def getParamEnv(suffix, default=None):
    return global_env.get(suffix, default)

try:
    p = subprocess.Popen(['/usr/bin/whoami'], stdout=subprocess.PIPE)
    line = p.stdout.readline()
    daemonuser = line.strip()
except:
    daemonuser = 'tagfiler'

# We want to share one global DB instance when pooling is enabled
shared_db = web.database(dbn=getParamEnv('dbnstr', 'postgres'),
                         db=getParamEnv('db', ''),
                         maxconnections=int(getParamEnv('dbmaxconnections', 8)))

if not shared_db.has_pooling:
    have_pooling = False
    shared_db = None
else:
    have_pooling = True
    
def get_db():
    if have_pooling:
        return shared_db
    else:
        return web.database(dbn=getParamEnv('dbnstr', 'postgres'), db=getParamEnv('db', ''))

class Application:
    "common parent class of all service handler classes to use db etc."
    __slots__ = [ 'dbnstr', 'dbstr', 'db', 'home', 'store_path', 'chunkbytes', 'render', 'help', 'jira', 'remap', 'webauthnexpiremins' ]

    def config_filler(self):
        def helper(config):
            config['policy remappings'] = buildPolicyRules(config['policy remappings'])
            return config
        return lambda : [ helper(config) for config in self.select_config(pred=web.Storage(tag='config', op=None, vals=[])) ]

    def select_config_cached(self, configname=None):
        if configname == None:
            configname = 'tagfiler'
        config = config_cache.select(self.db, self.config_filler(), None, configname)
        if config == None:
            return config_cache.select(self.db, self.config_filler(), None, 'tagfiler')
        else:
            return config

    def select_config(self, pred=None, params_and_defaults=None, fake_missing=True):
        
        if pred == None:
            pred = web.Storage(tag='config', op='=', vals=['tagfiler'])

        if params_and_defaults == None:
            params_and_defaults = [ ('applet custom properties', []),
                                    ('applet test properties', []),
                                    ('applet tags', []),
                                    ('applet tags require', []),
                                    ('applet test log', None),
                                    ('bugs', None),
                                    ('chunk bytes', 64 * 1024),
                                    ('client chunk bytes', 4194304),
                                    ('client socket timeout', 120),
                                    ('client connections', 2),
                                    ('client download chunks', False),
                                    ('client socket buffer size', 8192),
                                    ('client retry count', 10),
                                    ('client upload chunks', False),
                                    ('contact', None),
                                    ('enabled GUI features', []),
                                    ('file list tags', []),
                                    ('file list tags write', []),
                                    ('file write users', []),
                                    ('help', None),
                                    ('home', 'https://%s' % self.hostname),
                                    ('log path', '/var/www/%s-logs' % daemonuser),
                                    ('logo', ''),
                                    ('policy remappings', []),
                                    ('store path', '/var/www/%s-data' % daemonuser),
                                    ('subtitle', ''),
                                    ('tag list tags', []),
                                    ('tagdef write users', []),
                                    ('template path', '%s/tagfiler/templates' % distutils.sysconfig.get_python_lib()),
                                    ('webauthn home', None),
                                    ('webauthn require', 'False') ]

        results = self.select_files_by_predlist(subjpreds=[pred],
                                                tagdefs=Application.static_tagdefs,
                                                typedefs=Application.static_typedefs,
                                                listtags=[ "_cfg_%s" % key for key, default in params_and_defaults] + [ pred.tag, 'subject last tagged', 'subject last tagged txid' ],
                                                listas=dict([ ("_cfg_%s" % key, key) for key, default in params_and_defaults]))

        def set_defaults(config):
            for key, default in params_and_defaults:
                if config[key] == None or config[key] == []:
                    config[key] = default
            return config

        return [ set_defaults(config) for config in results ]

    def select_view_all(self):
        return self.select_files_by_predlist(subjpreds=[ web.Storage(tag='view', op=None, vals=[]) ],
                                             listtags=[ 'view' ] + [ "_cfg_%s" % key for key in ['file list tags', 'file list tags write', 'tag list tags'] ],
                                             listas=dict([ ("_cfg_%s" % key, key) for key in ['file list tags', 'file list tags write', 'tag list tags'] ]))

    def select_view(self, viewname=None, default='default'):
        return self.select_view_prioritized( [viewname, default] )
        
    def select_view_prioritized(self, viewnames=['default']):
        for viewname in viewnames:
            if viewname:
                view = view_cache.select(self.db, lambda : self.select_view_all(), self.authn.role, viewname)
                if view != None:
                    return view
        return None

    ops = [ ('', 'Tagged'),
            (':absent:', 'Tag absent'),
            ('=', 'Equal'),
            ('!=', 'Not equal'),
            (':lt:', 'Less than'),
            (':leq:', 'Less than or equal'),
            (':gt:', 'Greater than'),
            (':geq:', 'Greater than or equal'),
            (':like:', 'LIKE (SQL operator)'),
            (':simto:', 'SIMILAR TO (SQL operator)'),
            (':regexp:', 'Regular expression (case sensitive)'),
            (':!regexp:', 'Negated regular expression (case sensitive)'),
            (':ciregexp:', 'Regular expression (case insensitive)'),
            (':!ciregexp:', 'Negated regular expression (case insensitive)')]

    opsExcludeTypes = dict([ ('', []),
                             (':absent:', []),
                             ('=', ['empty']),
                             ('!=', ['empty']),
                             (':lt:', ['empty', 'boolean']),
                             (':leq:', ['empty', 'boolean']),
                             (':gt:', ['empty', 'boolean']),
                             (':geq:', ['empty', 'boolean']),
                             (':like:', ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean']),
                             (':simto:', ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean']),
                             (':regexp:', ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean']),
                             (':!regexp:', ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean']),
                             (':ciregexp:', ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean']),
                             (':!ciregexp:', ['empty', 'int8', 'float8', 'date', 'timestamptz', 'boolean']) ])

    opsDB = dict([ ('=', '='),
                   ('!=', '!='),
                   (':lt:', '<'),
                   (':leq:', '<='),
                   (':gt:', '>'),
                   (':geq:', '>='),
                   (':like:', 'LIKE'),
                   (':simto:', 'SIMILAR TO'),
                   (':regexp:', '~'),
                   (':!regexp:', '!~'),
                   (':ciregexp:', '~*'),
                   (':!ciregexp:', '!~*') ])
    
    # static representation of core schema
    static_typedefs = []
    for prototype in [ ('empty', '', 'No Content', None, []),
                       ('boolean', 'boolean', 'Boolean', None, ['T true', 'F false']),
                       ('int8', 'int8', 'Integer', None, []),
                       ('float8', 'float8', 'Floating point', None, []),
                       ('date', 'date', 'Date', None, []),
                       ('timestamptz', 'timestamptz', 'Date and time with timezone', None, []),
                       ('text', 'text', 'Text', None, []),
                       ('role', 'text', 'Role', None, []),
                       ('rolepat', 'text', 'Role pattern', None, []),
                       ('dtype', 'text', 'Dataset type', None, ['blank Dataset node for metadata-only',
                                                                'file Named dataset for locally stored file',
                                                                'url Named dataset for URL redirecting']),
                       ('url', 'text', 'URL', None, []),
                       ('id', 'int8', 'Subject ID or subquery', None, []),
                       ('tagpolicy', 'text', 'Tag policy model', None, ['anonymous Any client may access',
                                                                        'subject Subject authorization is observed',
                                                                        'subjectowner Subject owner may access',
                                                                        'tag Tag authorization is observed',
                                                                        'tagorsubject Tag or subject authorization is sufficient',
                                                                        'tagandsubject Tag and subject authorization are required',
                                                                        'system No client can access']),
                       ('type', 'text', 'Scalar value type', 'typedef', []),
                       ('tagdef', 'text', 'Tag definition', 'tagdef', []),
                       ('name', 'text', 'Subject name', 'latest with name', []),
                       ('vname', 'text', 'Subject name@version', 'vname', []),
                       ('view', 'text', 'View name', 'view', []),
                       ('template mode', 'text', 'Template rendering mode', None, ['embedded Embedded in Tagfiler HTML',
                                                                                   'page Standalone document']) ]:
        typedef, dbtype, desc, tagref, enum = prototype
        static_typedefs.append(web.Storage({'typedef' : typedef,
                                            'typedef description' : desc,
                                            'typedef dbtype' : dbtype,
                                            'typedef tagref' : tagref,
                                            'typedef values' : enum}))

    static_typedefs = dict( [ (typedef.typedef, typedef) for typedef in static_typedefs ] )
    static_tagdefs = []
    # -- the system tagdefs needed by the select_files_by_predlist call we make below and by Subject.populate_subject
    for prototype in [ ('config', 'text', False, 'subject', True),
                       ('id', 'int8', False, 'system', True),
                       ('tagdef', 'text', False, 'system', True),
                       ('tagdef type', 'type', False, 'system', False),
                       ('tagdef multivalue', 'boolean', False, 'system', False),
                       ('tagdef active', 'boolean', False, 'system', False),
                       ('tagdef readpolicy', 'tagpolicy', False, 'system', False),
                       ('tagdef writepolicy', 'tagpolicy', False, 'system', False),
                       ('tagdef unique', 'boolean', False, 'system', False),
                       ('tag read users', 'rolepat', True, 'subjectowner', False),
                       ('tag write users', 'rolepat', True, 'subjectowner', False),
                       ('typedef', 'text', False, 'subject', True),
                       ('typedef description', 'text', False, 'subject', False),
                       ('typedef dbtype', 'text', False, 'subject', False),
                       ('typedef values', 'text', True, 'subject', False),
                       ('typedef tagref', 'text', False, 'subject', False),
                       ('read users', 'rolepat', True, 'subjectowner', False),
                       ('write users', 'rolepat', True, 'subjectowner', False),
                       ('owner', 'role', False, 'subjectowner', False),
                       ('modified', 'timestamptz', False, 'system', False),
                       ('subject last tagged', 'timestamptz', False, 'system', False),
                       ('subject last tagged txid', 'int8', False, 'system', False),
                       ('tag last modified', 'timestamptz', False, 'system', False),
                       ('name', 'text', False, 'system', False),
                       ('version', 'int8', False, 'system', False),
                       ('latest with name', 'text', False, 'system', True),
                       ('_cfg_applet custom properties', 'text', True, 'subject', False),
                       ('_cfg_applet tags', 'tagdef', True, 'subject', False),
                       ('_cfg_applet tags require', 'tagdef', True, 'subject', False),
                       ('_cfg_applet test log', 'text', False, 'subject', False),
                       ('_cfg_applet test properties', 'text', True, 'subject', False),
                       ('_cfg_bugs', 'text', False, 'subject', False),
                       ('_cfg_chunk bytes', 'text', False, 'subject', False),
                       ('_cfg_client chunk bytes', 'int8', False, 'subject', False),
                       ('_cfg_client socket timeout', 'int8', False, 'subject', False),
                       ('_cfg_client connections', 'int8', False, 'subject', False),
                       ('_cfg_client download chunks', 'boolean', False, 'subject', False),
                       ('_cfg_client socket buffer size', 'int8', False, 'subject', False),
                       ('_cfg_client retry count', 'int8', False, 'subject', False),
                       ('_cfg_client upload chunks', 'boolean', False, 'subject', False),
                       ('_cfg_contact', 'text', False, 'subject', False),
                       ('_cfg_enabled GUI features', 'text', True, 'subject', False),
                       ('_cfg_file list tags', 'tagdef', True, 'subject', False),
                       ('_cfg_file list tags write', 'tagdef', True, 'subject', False),
                       ('_cfg_file write users', 'rolepat', True, 'subject', False),
                       ('_cfg_help', 'text', False, 'subject', False),
                       ('_cfg_home', 'text', False, 'subject', False),
                       ('_cfg_log path', 'text', False, 'subject', False),
                       ('_cfg_logo', 'text', False, 'subject', False),
                       ('_cfg_policy remappings', 'text', True, 'subject', False),
                       ('_cfg_store path', 'text', False, 'subject', False),
                       ('_cfg_subtitle', 'text', False, 'subject', False),
                       ('_cfg_tag list tags', 'tagdef', True, 'subject', False),
                       ('_cfg_tagdef write users', 'rolepat', True, 'subject', False),
                       ('_cfg_template path', 'text', False, 'subject', False),
                       ('_cfg_webauthn home', 'text', False, 'subject', False),
                       ('_cfg_webauthn require', 'boolean', False, 'subject', False) ]:
        deftagname, typestr, multivalue, writepolicy, unique = prototype
        static_tagdefs.append(web.Storage(tagname=deftagname,
                                          owner=None,
                                          typestr=typestr,
                                          dbtype=static_typedefs[typestr]['typedef dbtype'],
                                          multivalue=multivalue,
                                          active=True,
                                          readpolicy='anonymous',
                                          readok=True,
                                          writepolicy=writepolicy,
                                          unique=unique,
                                          tagreaders=[],
                                          tagwriters=[]))

    static_tagdefs = dict( [ (tagdef.tagname, tagdef) for tagdef in static_tagdefs ] )

    rfc1123 = '%a, %d %b %Y %H:%M:%S UTC%z'

    def set_http_etag(self, txid):
        """Set an ETag from txid as main version key.

        """
        etag = []
        if 'Cookie' in self.http_vary:
            etag.append( '%s' % self.authn.role )
        else:
            etag.append( '*' )
            
        if 'Accept' in self.http_vary:
            etag.append( '%s' % web.ctx.env.get('HTTP_ACCEPT', '') )
        else:
            etag.append( '*' )

        etag.append( '%s' % txid )

        self.http_etag = '"%s"' % ';'.join(etag).replace('"', '\\"')
        #web.debug(self.http_etag)

    def http_is_cached(self):
        """Determine whether a request is cached and the request can return 304 Not Modified.
           Currently only considers ETags via HTTP "If-None-Match" header, if caller set self.http_etag.
        """
        def etag_parse(s):
            strong = True
            if s[0:2] == 'W/':
                strong = False
                s = s[2:]
            return (s, strong)

        def etags_parse(s):
            etags = []
            while s:
                s = s.strip()
                m = re.match('^,? *(?P<first>(W/)?"(.|\\")*")(?P<rest>.*)', s)
                if m:
                    g = m.groupdict()
                    etags.append(etag_parse(g['first']))
                    s = g['rest']
                else:
                    s = None
            return dict(etags)
        
        client_etags = etags_parse( web.ctx.env.get('HTTP_IF_NONE_MATCH', ''))
        #web.debug(client_etags)
        
        if client_etags.has_key('"*"'):
            return True
        if client_etags.has_key('%s' % self.http_etag):
            return True

        return False

    def __init__(self, parser=None, queryopts=None):
        "store common configuration data for all service classes"
        global render
        global db_cache

        def long2str(x):
            s = ''

        if hasattr(self, 'content_range'):
            return
            
        self.content_range = None
        self.last_log_time = 0
        self.start_time = datetime.datetime.now(pytz.timezone('UTC'))

        self.emitted_headers = dict()
        self.http_vary = set(['Cookie'])
        self.http_etag = None

        self.request_guid = base64.b64encode(  struct.pack('Q', random.getrandbits(64)) )

        self.url_parse_func = parser

        self.skip_preDispatch = False

        self.version = None
        self.subjpreds = []
        self.globals = dict()

        if queryopts == None:
            self.queryopts = dict()
        else:
            self.queryopts = queryopts

        # this will interfere with internal queries
        if self.queryopts.has_key('range'):
            self.query_range = self.queryopts['range']
            del self.queryopts['range']
        else:
            self.query_range = None

        # this ordered list can be pruned to optimize transactions
        self.needed_db_globals = [  'typeinfo', 'typesdict', 'tagdefsdict', 'roleinfo' ]

        myAppName = os.path.basename(web.ctx.env['SCRIPT_NAME'])

        self.hostname = socket.gethostname()

        self.logmsgs = []
        self.middispatchtime = None

        self.db = get_db()

        # BEGIN: get runtime parameters from database
        self.globals['tagdefsdict'] = Application.static_tagdefs # need these for select_config() below
        # set default anonymous authn info
        self.set_authn(webauthn.providers.AuthnInfo(None, set([]), None, None, False, None))
        #self.log('TRACE', 'Application() constructor after static defaults')

        # get full config
        self.config = config_cache.select(self.db, self.config_filler(), None, 'tagfiler')

        #self.log('TRACE', 'Application() self.config loaded')
        del self.globals['tagdefsdict'] # clear this so it will be rebuilt properly during transaction
        
        self.render = web.template.render(self.config['template path'], globals=self.globals)
        render = self.render # HACK: make this available to exception classes too

        def sq_path_linearize(v):
            if hasattr(v, 'is_subquery'):
                return path_linearize(v.path)
            else:
                return v
        
        # 'globals' are local to this Application instance and also used by its templates
        self.globals['smartTagValues'] = True
        self.globals['render'] = self.render # HACK: make render available to templates too
        self.globals['urlquote'] = urlquote
        self.globals['idquote'] = idquote
        self.globals['webdebug'] = web.debug
        self.globals['jsonWriter'] = jsonWriter
        self.globals['subject2identifiers'] = lambda subject, showversions=True: self.subject2identifiers(subject, showversions)
        self.globals['sq_path_linearize'] = sq_path_linearize

        self.globals['home'] = self.config.home + web.ctx.homepath
        self.globals['homepath'] = web.ctx.homepath

        # copy many config values to globals map for templates
        self.globals['config'] = self.config
        self.globals['help'] = self.config.help
        self.globals['bugs'] = self.config.bugs
        self.globals['subtitle'] = self.config.subtitle
        self.globals['logo'] = self.config.logo
        self.globals['contact'] = self.config.contact
        self.globals['webauthnhome'] = self.config['webauthn home']
        self.globals['webauthnrequire'] = self.config['webauthn require']
        self.globals['filelisttags'] = self.config['file list tags']
        self.globals['filelisttagswrite'] = self.config['file list tags write']
        self.globals['appletTestProperties'] = self.config['applet test properties']
        self.globals['appletLogfile'] = self.config['applet test log']
        self.globals['appletCustomProperties'] = self.config['applet custom properties']
        self.globals['clientChunkbytes'] = self.config['client chunk bytes']
        self.globals['clientSocketTimeout'] = self.config['client socket timeout']
        self.globals['clientConnections'] = self.config['client connections']
        self.globals['clientUploadChunks'] = self.config['client upload chunks']
        self.globals['clientDownloadChunks'] = self.config['client download chunks']
        self.globals['clientSocketBufferSize'] = self.config['client socket buffer size']
        self.globals['clientRetryCount'] = self.config['client retry count']
        self.globals['enabledGUIFeatures'] = self.config['enabled GUI features']
        self.globals['browsersImmutableTags'] = [ 'check point offset', 'key', 'sha256sum' ]
        
        # END: get runtime parameters from database
        #self.log('TRACE', 'Application() config unpacked')

        try:
            def parsekv(kv):
                if len(kv) == 2:
                    return kv
                else:
                    return [ kv[0], None ]
                
            uri = web.ctx.env['REQUEST_URI']
            self.storage = web.storage([ parsekv(kv.split('=', 1)) for kv in uri.split('?', 1)[1].replace(';', '&').split('&') ])
        except:
            self.storage = web.storage([]) 
        #self.log('TRACE', 'Application() constructor exiting')

    def header(self, name, value):
        web.header(name, value)
        self.emitted_headers[name.lower()] = value

    def emit_headers(self):
        """Emit any automatic headers prior to body beginning."""
        if self.http_vary:
            self.header('Vary', ', '.join(self.http_vary))
        if self.http_etag:
            self.header('ETag', '%s' % self.http_etag)

    def validateSubjectQuery(self, query, tagdef=None, subject=None):
        if type(query) in [ int, long ]:
            return query
        if query in [ None, [] ]:
            return query
        if type(query) in [ type('string'), unicode ]:
            ast = self.url_parse_func(query)
            if type(ast) in [ int, long ]:
                # this is a bare subject identifier
                return ast
            elif hasattr(ast, 'is_subquery'):
                query = ast
        if hasattr(query, 'is_subquery') and query.is_subquery:
            # this holds a subquery expression to evaluate
            return [ subject.id for subject in self.select_files_by_predlist_path(path=query.path) ]
        raise BadRequest(self, 'Sub-query expression "%s" not a valid expression.' % query)
        
    def validateFilename(self, file, tagdef='', subject=None):        
        results = self.select_files_by_predlist(subjpreds=[web.Storage(tag='name', op='=', vals=[file])],
                                                listtags=['id'])
        if len(results) == 0:
            raise Conflict(self, 'Supplied file name "%s" for tag "%s" is not found.' % (file, tagdef.tagname))

    def validateVersionedFilename(self, vfile, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        m = re.match('^(?P<data_id>.*)@(?P<version>[0-9]+)', vfile)
        if m:
            g = m.groupdict()
            try:
                version = int(g['version'])
            except ValueError:
                raise BadRequest(self, 'Supplied versioned file name "%s" for tag "%s" has an invalid version suffix.' % (vfile, tagname))
            if g['data_id'] == '':
                raise BadRequest(self, 'Supplied versioned file name "%s" for tag "%s" has an invalid name.' % (vfile, tagname))
            results = self.select_files_by_predlist(subjpreds=[web.Storage(tag='vname', op='=', vals=[vfile]),
                                                              web.Storage(tag='version', op='=', vals=[version])],
                                                    listtags=['id'],
                                                    versions='any')
            if len(results) == 0:
                raise Conflict(self, 'Supplied versioned file name "%s" for tag "%s" is not found.' % (vfile, tagname))
        else:
            raise BadRequest(self, 'Supplied versioned file name "%s" for tag "%s" has invalid syntax.' % (vfile, tagname))

    def validateTagname(self, tag, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        if tag == '':
            raise Conflict(self, 'You must specify a defined tag name to set values for "%s".' % tagname)
        results = self.select_tagdef(tag)
        if len(results) == 0:
            raise Conflict(self, 'Supplied tag name "%s" is not defined.' % tag)

    def validateRole(self, role, tagdef=None, subject=None):
        if self.authn:
            try:
                valid = self.authn.roleProvider.testRole(self.db, role)
            except NotImplemented, AttributeError:
                valid = True
            if not valid:
                #web.debug('Supplied tag value "%s" is not a valid role.' % role)
                raise Conflict(self, 'Supplied tag value "%s" is not a valid role.' % role)
                
    def validateRolePattern(self, role, tagdef=None, subject=None):
        if role in [ '*' ]:
            return
        return self.validateRole(role)

    def validateEnumeration(self, enum, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        try:
            key, desc = enum.split(" ", 1)
            key = urlunquote(key)
        except:
            raise BadRequest(self, 'Supplied enumeration value "%s" does not have key and description fields.' % enum)

        if tagname == 'typedef values':
            results = self.gettagvals(subject, self.globals['tagdefsdict']['typedef'])
            if len(results) == 0:
                raise Conflict(self, 'Set the "typedef" tag before trying to set "typedef values".')
            typename = results[0]
            type = typedef_cache.select(self.db, lambda: self.get_type(), self.authn.role, typename)
            if type == None:
                raise Conflict(self, 'The type "%s" is not defined!' % typename)
            dbtype = type['typedef dbtype']
            try:
                key = downcast_value(dbtype, key)
            except:
                raise BadRequest(self, data='The key "%s" cannot be converted to type "%s" (%s).' % (key, type['typedef description'], dbtype))

    def validatePolicyRule(self, rule, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        try:
            remap = buildPolicyRules([rule], fatal=True)
        except (ValueError, KeyError):
            raise BadRequest(self, 'Supplied rule "%s" is invalid for tag "%s".' % (rule, tagname))
        srcrole, mapping = remap.items()[0]
        if self.config['policy remappings'].has_key(srcrole):
            raise BadRequest(self, 'Supplied rule "%s" duplicates already mapped source role "%s".' % (rule, srcrole))

    def doPolicyRule(self, newfile):
        srcroles = set(self.config['policy remappings'].keys()).intersection(self.authn.roles)
        if len(srcroles) == 1:
            try:
                t = self.db.transaction()
                srcrole = srcroles.pop()
                dstrole, readusers, writeusers, readok, writeok = self.config['policy remappings'][srcrole]
                readusers = [ u for u in readusers ]
                writeusers = [ u for u in writeusers ]
                #web.debug(self.remap)
                #web.debug('remap:', self.remap[srcrole])
                self.delete_tag(newfile, self.globals['tagdefsdict']['read users'])
                if readok:
                    readusers.append( self.authn.role )
                if writeok:
                    writeusers.append( self.authn.role )
                for readuser in readusers:
                    self.set_tag(newfile, self.globals['tagdefsdict']['read users'], readuser)
                self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='read users', value=','.join(readusers))
                self.delete_tag(newfile, self.globals['tagdefsdict']['write users'])
                for writeuser in writeusers:
                    self.set_tag(newfile, self.globals['tagdefsdict']['write users'], writeuser)
                self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='write users', value=','.join(writeusers))
                if dstrole:
                    self.set_tag(newfile, self.globals['tagdefsdict']['owner'], dstrole)
                self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='owner', value=dstrole)
                t.commit()
            except:
                et, ev, tb = sys.exc_info()
                web.debug('got exception "%s" during owner remap attempt' % str(ev),
                          traceback.format_exception(et, ev, tb))
                t.rollback()
                raise
        elif len(srcroles) > 1:
            raise Conflict(self, "Ambiguous remap rules encountered.")

    def logfmt_old(self, action, dataset=None, tag=None, mode=None, user=None, value=None, txid=None):
        parts = []
        if dataset:
            parts.append('dataset "%s"' % dataset)
        if tag:
            parts.append('tag "%s"' % tag)
        if value:
            parts.append('value "%s"' % value)
        if mode:
            parts.append('mode "%s"' % mode)
        if txid:
            parts.append('last changed "%s"' % txid)

        return ('%s ' % action) + ', '.join(parts)

    def lograw(self, msg):
        logger.info(myutf8(msg))

    def logfmt(self, action, dataset=None, tag=None, mode=None, user=None, value=None, txid=None):
        if self.start_time:
            now = datetime.datetime.now(pytz.timezone('UTC'))
            elapsed = u'%d.%3.3d' % ( (now - self.start_time).seconds, (now - self.start_time).microseconds / 1000 )
            self.last_log_time = now
        else:
            elapsed = '-.---'
        return u'%ss %s%s req=%s -- %s' % (elapsed, web.ctx.ip, self.authn.role and u' user=%s' % urlquote(self.authn.role) or u'', 
                                      self.request_guid, self.logfmt_old(action, dataset, tag, mode, user, value, txid))

    def log(self, action, dataset=None, tag=None, mode=None, user=None, value=None, txid=None):
        self.lograw(self.logfmt(action, dataset, tag, mode, user, value, txid))

    def txlog(self, action, dataset=None, tag=None, mode=None, user=None, value=None, txid=None):
        self.logmsgs.append(self.logfmt(action, dataset, tag, mode, user, value, txid))

    def set_authn(self, authn):
        if not hasattr(self, 'authn'):
            self.authn = None
        #web.debug(self.authn, authn)
        self.authn = authn
        self.globals['authn'] = authn

    def renderlist(self, title, renderlist, refresh=True):
        if refresh:
            self.globals['pollmins'] = 1
        else:
            self.globals['pollmins'] = None

        self.globals['title'] = title

        yield self.render.Top()

        for r in renderlist:
            yield r

        yield self.render.Bottom()
 
    def preDispatchFake(self, uri, app):
        self.db = app.db
        self.set_authn(app.authn)

    def preDispatchCore(self, uri, setcookie=True):
        self.request_uri = uri
        if self.globals['webauthnhome']:
            if not self.db:
                self.db = get_db()
            t = self.db.transaction()
            try:
                self.set_authn(webauthn.session.test_and_update_session(self.db,
                                                                        referer=self.config.home + uri,
                                                                        setcookie=setcookie))
                t.commit()
            except:
                t.rollback()
                raise

            self.middispatchtime = datetime.datetime.now()
            if not self.authn.role and self.globals['webauthnrequire']:
                raise web.seeother(self.globals['webauthnhome'] + '/login?referer=%s' % urlquote(self.config.home + uri))
        else:
            try:
                user = web.ctx.env['REMOTE_USER']
                roles = set([ user ])
            except:
                user = None
                roles = set()
            self.set_authn(webauthn.providers.AuthnInfo(user, roles, None, None, False, None))

    def preDispatch(self, uri):
        self.preDispatchCore(uri)

    def postDispatch(self, uri=None):
        def body():
            if self.globals['webauthnhome']:
                t = self.db.transaction()
                try:
                    webauthn.session.test_and_update_session(self.db, self.authn.guid,
                                                             ignoremustchange=True,
                                                             setcookie=False)
                    t.commit()
                except:
                    t.rollback()
                    raise

        def postCommit(results):
            pass

        self.dbtransact(body, postCommit)

    def midDispatch(self):
        now = datetime.datetime.now()
        if self.middispatchtime == None or (now - self.middispatchtime).seconds > 30:
            self.preDispatchCore(web.ctx.homepath, setcookie=False)

    def setNoCache(self):
        now = datetime.datetime.now(pytz.timezone('UTC'))
        now_rfc1123 = now.strftime(Application.rfc1123)
        self.header('Cache-control', 'no-cache')
        self.header('Expires', now_rfc1123)

    def logException(self, context=None):
        if context == None:
            context = 'unspecified'
        et, ev, tb = sys.exc_info()
        web.debug('exception "%s"' % context,
                  traceback.format_exception(et, ev, tb))

    def dbquery(self, query, vars={}):
        return db_dbquery(self.db, query, vars=vars)

    def dbtransact(self, body, postCommit):
        """re-usable transaction pattern

           using caller-provided thunks under boilerplate
           commit/rollback/retry logic
        """
        if not self.db:
            self.db = get_db()

        #self.log('TRACE', value='dbtransact() entered')

        try:
            count = 0
            limit = 8
            error = None
            while True:
                count = count + 1
                try:
                    t = self.db.transaction()
                    
                    try:
                        self.logmsgs = []
                        self.subject = None
                        self.datapred = None
                        self.dataname = None
                        self.dataid = None

                        # build up globals useful to almost all classes, to avoid redundant coding
                        # this is fragile to make things fast and simple
                        db_globals_dict = dict(roleinfo=lambda : [],
                                               typeinfo=lambda : [ x for x in typedef_cache.select(self.db, lambda: self.get_type(), self.authn.role)],
                                               typesdict=lambda : dict([ (type['typedef'], type) for type in self.globals['typeinfo'] ]),
                                               tagdefsdict=lambda : dict([ (tagdef.tagname, tagdef) for tagdef in tagdef_cache.select(self.db, lambda: self.select_tagdef(), self.authn.role) ]) )
                        #self.log('TRACE', value='preparing needed_db_globals')
                        for key in self.needed_db_globals:
                            if not self.globals.has_key(key):
                                self.globals[key] = db_globals_dict[key]()
                                #self.log('TRACE', value='prepared %s' % key)

                        #self.log('TRACE', 'needed_db_globals loaded')
                        
                        def tagOptions(tagname, values=[]):
                            tagdef = self.globals['tagdefsdict'][tagname]
                            tagnames = self.globals['tagdefsdict'].keys()
                            type = self.globals['typesdict'][tagdef.typestr]
                            typevals = type['typedef values']
                            tagref = type['typedef tagref']

                            if typevals:
                                options = True
                            elif tagdef.typestr in [ 'role', 'rolepat' ]:
                                options = True
                            elif tagref:
                                if tagref in tagnames:
                                    options = True
                                else:
                                    options = None
                            elif tagdef.typestr == 'tagname' and tagnames:
                                options = True
                            else:
                                options = None
                            return options

                        self.globals['tagOptions'] = tagOptions
                        #self.log('TRACE', 'dbtransact() tagOptions loaded')

                        # and set defaults if they weren't overridden by caller
                        for globalname, default in [ ('view', None),
                                                     ('referer', web.ctx.env.get('HTTP_REFERER', None)),
                                                     ('tagspace', 'tags'),
                                                     ('datapred', self.datapred),
                                                     ('dataname', self.dataname),
                                                     ('dataid', self.dataid) ]:
                            current = self.globals.get(globalname, None)
                            if not current:
                                self.globals[globalname] = default

                        #self.log('TRACE', 'dbtransact() all globals loaded')
                        bodyval = body()
                        t.commit()
                        break
                        # syntax "Type as var" not supported by Python 2.4
                    except (psycopg2.InterfaceError), te:
                        # pass this to outer handler
                        error = str(te)
                        web.debug('got psycopg2.InterfaceError "%s"' % error)
                        et, ev, tb = sys.exc_info()
                        web.debug('got exception "%s" during dbtransact' % str(ev),
                                  traceback.format_exception(et, ev, tb))
                        raise te
                    except (web.SeeOther), te:
                        t.commit()
                        raise te
                    except (NotFound, BadRequest, Unauthorized, Forbidden, Conflict), te:
                        t.rollback()
                        raise te
                    except (psycopg2.DataError, psycopg2.ProgrammingError), te:
                        t.rollback()
                        et, ev, tb = sys.exc_info()
                        web.debug('got exception "%s" during dbtransact' % str(ev),
                                  traceback.format_exception(et, ev, tb))
                        raise BadRequest(self, data='Logical error: %s.' % str(te))
                    except TypeError, te:
                        t.rollback()
                        et, ev, tb = sys.exc_info()
                        web.debug('got exception "%s" during dbtransact' % str(ev),
                                  traceback.format_exception(et, ev, tb))
                        raise RuntimeError(self, data=str(te))
                    except (psycopg2.IntegrityError, psycopg2.extensions.TransactionRollbackError), te:
                        t.rollback()
                        error = str(te)
                        if count > limit:
                            # retry on version key violation, can happen under concurrent uploads
                            raise IntegrityError(self, data=error)
                    except (IOError), te:
                        t.rollback()
                        error = str(te)
                        if count > limit:
                            raise RuntimeError(self, data=error)
                        # else fall through to retry...
                    except:
                        t.rollback()
                        et, ev, tb = sys.exc_info()
                        web.debug('got unmatched exception in dbtransact',
                                  traceback.format_exception(et, ev, tb),
                                  ev)
                        raise

                except psycopg2.InterfaceError:
                    # try reopening the database connection
                    web.debug('got psycopg2.InterfaceError')
                    et, ev, tb = sys.exc_info()
                    web.debug('got exception "%s" during dbtransact' % str(ev),
                              traceback.format_exception(et, ev, tb))
                    self.db = get_db()

                # exponential backoff...
                # count=1 is roughly 0.1 microsecond
                # count=9 is roughly 10 seconds
                # randomly jittered from 75-125% of exponential delay
                if count > limit:
                    raise RuntimeError(self, data='Exceeded retry limit with error "%s".' % error)
                delay =  random.uniform(0.75, 1.25) * math.pow(10.0, count) * 0.00000001
                web.debug('transaction retry: delaying %f on "%s"' % (delay, error))
                time.sleep(delay)

        finally:
            pass
                    
        for msg in self.logmsgs:
            logger.info(myutf8(msg))
        self.logmsgs = []
        return postCommit(bodyval)

    def acceptPair(self, s):
        parts = s.split(';')
        q = 1.0
        t = parts[0]
        for p in parts[1:]:
            fields = p.split('=')
            if len(fields) == 2 and fields[0] == 'q':
                q = fields[1]
        return (q, t)
        
    def acceptTypesPreferedOrder(self):
        try:
            accept = web.ctx.env['HTTP_ACCEPT']
        except:
            accept = ""
            
        return [ pair[1]
                 for pair in
                 sorted([ self.acceptPair(s) for s in accept.lower().split(',') ],
                        key=lambda pair: pair[0]) ]

    # a bunch of little database access helpers for this app, to be run inside
    # the dbtransact driver

    def validate_subjpreds_unique(self, acceptName=False, acceptBlank=False, restrictSchema=False, subjpreds=None):
        """Evaluate subjpreds (default self.subjpreds) for subject-identifying uniqueness.

           Raises Conflict if restrictSchema=True and additional
           criteria are not met:

              1. no preds are ambiguous, e.g. can be used with set_tag
              2. no preds involve writeok=False tagdefs

           Returns (in prioritized order):

              True if subjpreds is uniquely constraining

              False if subjpreds is weakly constraining AND acceptName==True

              None if subjpreds is not constraining AND acceptBlank==True

           Else raises Conflict

        """
        if subjpreds == None:
            subjpreds = self.subjpreds
        got_name = False
        got_version = False
        unique = None
        for pred in subjpreds:
            tagdef = self.globals['tagdefsdict'].get(pred.tag, None)
            if tagdef == None:
                raise Conflict(self, 'Tag "%s" referenced in subject predicate list is not defined on this server.' % pred.tag)

            if restrictSchema:
                if tagdef.tagname not in [ 'name', 'version' ] and tagdef.writeok == False:
                    raise Conflict(self, 'Subject predicate sets restricted tag "%s".' % tagdef.tagname)
                if tagdef.typestr == 'empty' and pred.op or \
                       tagdef.typestr != 'empty' and pred.op != '=':
                    raise Conflict(self, 'Subject predicate has inappropriate operator "%s" on tag "%s".' % (pred.op, tagdef.tagname))
                    
            if tagdef.get('unique', False) and pred.op == '=' and pred.vals:
                unique = True
            elif tagdef.tagname == 'name' and pred.op == '=' and pred.vals:
                got_name = True
            elif tagdef.tagname == 'version' and pred.op == '=' and pred.vals:
                got_version = True
                
        if got_name and got_version:
            unique = True

        if unique:
            return True
        elif got_name and acceptName:
            return False
        elif acceptBlank:
            return None
        else:
            raise Conflict(self, 'Subject-identifying predicate list requires a unique identifying constraint.')

    def test_file_authz(self, mode, subject):
        """Check whether access is allowed to user given mode and owner.

           True: access allowed
           False: access forbidden
           None: user needs to authenticate to be sure"""
        status = web.ctx.status

        # read is authorized or subject would not be found
        if mode == 'write':
            if len(set(self.authn.roles)
                   .union(set(['*']))
                   .intersection(set(subject['write users'] or []))) > 0:
                return True
            elif self.authn.role:
                return False
            else:
                return None
        else:
            return True

    def test_tag_authz(self, mode, subject, tagdef):
        """Check whether access is allowed to user given policy_tag and owner.

           True: access allowed
           False: access forbidden
           None: user needs to authenticate to be sure
                 or subject is None and subject is needed to make determination"""
        policy = tagdef['%spolicy' % mode]

        tag_ok = tagdef.owner in self.authn.roles \
                 or len(set([ r for r in self.authn.roles])
                        .union(set(['*']))
                        .intersection(set(tagdef['tag' + mode[0:4] + 'ers'] or []))) > 0

        if subject:
            subject_ok = dict(read=True, write=subject.writeok)[mode]
            subject_owner = subject.owner in self.authn.roles
        else:
            subject_ok = None
            subject_owner = None
        
        if policy == 'system':
            return False
        elif policy == 'subjectowner':
            return subject_owner
        elif policy == 'subject':
            return subject_ok
        elif policy == 'tagandsubject':
            return tag_ok and subject_ok
        elif policy == 'tagorsubject':
            return tag_ok or subject_ok
        elif policy == 'tag':
            return tag_ok
        else:
            # policy == 'anonymous'
            return True

    def test_tagdef_authz(self, mode, tagdef):
        """Check whether access is allowed."""
        if mode == 'read':
            return True
        elif self.authn.role:
            return tagdef.owner in self.authn.roles
        else:
            return None

    def enforce_file_authz(self, mode, subject):
        """Check whether access is allowed and throw web exception if not."""
        allow = self.test_file_authz(mode, subject)
        data = '%s of dataset "%s"' % self.subject2identifiers(subject)[0]
        if allow == False:
            raise Forbidden(self, data=data)
        elif allow == None:
            raise Unauthorized(self, data=data)

    def enforce_tag_authz(self, mode, subject, tagdef):
        """Check whether access is allowed and throw web exception if not."""
        allow = self.test_tag_authz(mode, subject, tagdef)
        data = '%s of tag "%s" on dataset "%s"' % (mode, tagdef.tagname, self.subject2identifiers(subject)[0])
        if allow == False:
            raise Forbidden(self, data=data)
        elif allow == None:
            raise Unauthorized(self, data=data)

    def enforce_tagdef_authz(self, mode, tagdef):
        """Check whether access is allowed and throw web exception if not."""
        allow = self.test_tagdef_authz(mode, tagdef)
        data = '%s of tagdef="%s"' % (mode, tagdef.tagname)
        if allow == False:
            raise Forbidden(self, data=data)
        elif allow == None:
            raise Unauthorized(self, data=data)

    def wraptag(self, tagname, suffix='', prefix='_'):
        return '"' + prefix + tagname.replace('"','""') + suffix + '"'

    def classify_subject(self, subject):
        for dtype in [ 'url', 'tagdef', 'typedef', 'config', 'view', 'file', 'name' ] \
                + [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique and tagdef.tagname if tagdef.tagname != 'id' ] \
                + [ 'id' ] :
            keyv = subject.get(dtype, None)
            if keyv:
                return dtype

    def subject2identifiers(self, subject, showversions=True):
        try:
            # try to follow dtype from DB
            dtype = subject.dtype
        except:
            dtype = self.classify_subject(subject)

        name = subject.get('name', None)
        version = subject.get('version', None)
        datapred = None
        dataid = None
        dataname = None
        if name != None:
            if version != None and showversions:
                datapred = 'name=%s;version=%s' % (urlquote(name), version) 
                dataid = datapred
                dataname = '%s;version=%s' % (name, version)
            else:
                datapred = 'name=%s' % urlquote(name)
                dataid = datapred
                dataname = name
        else:
            if dtype not in [ 'file', 'url' ]:
                keyv = subject.get(dtype, None)
            else:
                keyv = None

            if keyv:
                if self.globals['tagdefsdict'][dtype].multivalue:
                    keyv = keyv[0]
                datapred = '%s=%s' % (urlquote(dtype), urlquote(keyv))
                dataid = datapred
                dataname = '%s=%s' % (dtype, keyv)
                effective_dtype = dtype
            else:
                # tags weren't projected, so treat as 'id' as fallback
                effective_dtype = 'id'

            if effective_dtype == 'id':
                datapred = 'id=%s' % subject.id
                dataid = datapred
                dataname = datapred

        return (datapred, dataid, dataname, dtype)

    def get_type(self, typename=None):
        def valexpand(res):
            # replace raw "key desc" string with (key, desc) pair
            if res['typedef values'] != None:
                vals = []
                for val in res['typedef values']:
                    key, desc = val.split(" ", 1)
                    key = urlunquote(key)
                    dbtype = res['typedef dbtype']
                    key = downcast_value(dbtype, key)
                    vals.append( (key, desc) )
                res['typedef values'] = dict(vals)
            return res
        if typename != None:
            subjpreds = [ web.Storage(tag='typedef', op='=', vals=[typename]) ]
        else:
            subjpreds = [ web.Storage(tag='typedef', op=None, vals=[]) ]
        listtags = [ 'typedef', 'typedef description', 'typedef dbtype', 'typedef values', 'typedef tagref' ]
        return [ valexpand(res) for res in self.select_files_by_predlist(subjpreds=subjpreds, listtags=listtags, tagdefs=Application.static_tagdefs, typedefs=Application.static_typedefs) ]

    def select_file_members(self, subject, membertag='vcontains'):
        # return the children of the dataset as referenced by its membertag, e.g. vcontains or contains
        if membertag == 'contains':
            versions = 'latest'
        else:
            versions = 'any'
        return self.select_files_by_predlist_path([ ([ web.Storage(tag='id', op='=', vals=[subject.id]) ], [ membertag ], [ ]),
                                                    ( [], [], [] ) ],
                                                  versions=versions)

    def select_file_versions(self, name):
        vars = dict(name=name)
        query = 'SELECT n.subject AS id, n.value AS file, v.value AS version FROM "_name" AS n JOIN "_version" AS v USING (subject)' \
                 + ' WHERE n.value = $name'
        return self.dbquery(query, vars)

    def select_dataset_size(self, key, membertag='vcontains'):
        # return statistics aout the children of the dataset as referenced by its membertag
        query, values = self.build_files_by_predlist_path([ ([web.Storage(tag='key', op='=', vals=[key])], [web.Storage(tag=membertag,op=None,vals=[])], []),
                                                            ([], [ web.Storage(tag=tag,op=None,vals=[]) for tag in 'name', 'bytes' ], []) ])
        query = 'SELECT SUM(bytes) AS size, COUNT(*) AS count FROM (%s) AS q' % query
        return self.dbquery(query, values)

    def insert_file(self, name, version, file=None):
        newid = self.dbquery("INSERT INTO resources DEFAULT VALUES RETURNING subject")[0].subject
        subject = web.Storage(id=newid)
        
        self.set_tag_lastmodified(subject, self.globals['tagdefsdict']['id'])

        if version:
            self.set_tag(subject, self.globals['tagdefsdict']['version'], version)

        if name:
            self.set_tag(subject, self.globals['tagdefsdict']['name'], name)

            if version > 1:
                self.update_latestfile_version(name, newid)
            elif version == 1:
                self.set_tag(subject, self.globals['tagdefsdict']['latest with name'], name)

        if file:
            self.set_tag(subject, self.globals['tagdefsdict']['file'], file)

        return newid

    def update_latestfile_version(self, name, next_latest_id):
        vars=dict(name=name, id=next_latest_id)
        self.dbquery('UPDATE "_latest with name" SET subject = $id WHERE value = $name', vars=vars)

    def delete_file(self, subject, allow_tagdef=False):
        wheres = []

        if subject.get('tagdef', None) != None and not allow_tagdef:
            raise Conflict(self, u'Delete of subject tagdef="' + subject.tagdef  + u'" not supported; use dedicated /tagdef/ API.')

        if subject.name and subject.version:
            versions = [ file for file in self.select_file_versions(subject.name) ]
            versions.sort(key=lambda res: res.version, reverse=True)

            latest = versions[0]
        
            if subject.version == latest.version and len(versions) > 1:
                # we're deleting the latest version and there are previous versions
                self.update_latestfile_version(subject.name, versions[1].id)

        results = self.dbquery('SELECT * FROM subjecttags WHERE subject = $subject', vars=dict(subject=subject.id))
        for result in results:
            self.set_tag_lastmodified(None, self.globals['tagdefsdict'][result.tagname])
        self.set_tag_lastmodified(None, self.globals['tagdefsdict']['id'])
        
        query = 'DELETE FROM resources WHERE subject = $id'
        self.dbquery(query, vars=dict(id=subject.id))

    tagdef_listas =  { 'tagdef': 'tagname', 
                       'tagdef type': 'typestr', 
                       'tagdef multivalue': 'multivalue',
                       'tagdef active': 'active',
                       'tagdef readpolicy': 'readpolicy',
                       'tagdef writepolicy': 'writepolicy',
                       'tagdef unique': 'unique',
                       'tag read users': 'tagreaders',
                       'tag write users': 'tagwriters',
                       'tag last modified': 'modified' }

    def select_tagdef(self, tagname=None, subjpreds=[], order=None, enforce_read_authz=True):
        listtags = [ 'owner' ]
        listtags = listtags + Application.tagdef_listas.keys()

        if order:
            if type(order) == tuple:
                ordertags = [ order ]
            else:
                ordertags = [ ( order, ':asc:') ]
        else:
            ordertags = []

        def augment(tagdef):
            for mode in ['read', 'write']:
                tagdef['%sok' % mode] = self.test_tag_authz(mode, None, tagdef)

            try:
                typedef = self.globals['typesdict'][tagdef.typestr]
            except:
                typedef = Application.static_typedefs[tagdef.typestr]
                
            tagdef['tagref'] = typedef['typedef tagref']
            tagdef['dbtype'] = typedef['typedef dbtype']
            
            return tagdef
            
        if tagname:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op='=', vals=[tagname]) ]
        else:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op=None, vals=[]) ]

        results = [ augment(tagdef) for tagdef in self.select_files_by_predlist(subjpreds, listtags, ordertags, listas=Application.tagdef_listas, tagdefs=Application.static_tagdefs, typedefs=Application.static_typedefs, enforce_read_authz=enforce_read_authz) ]
        #web.debug(results)
        return results

    def insert_tagdef(self):
        results = self.select_tagdef(self.tag_id)
        if len(results) > 0:
            raise Conflict(self, 'Tagdef "%s" already exists. Delete it before redefining.' % self.tag_id)

        owner = self.authn.role
        newid = self.insert_file(None, None, None)
        subject = web.Storage(id=newid)
        tags = [ ('created', 'now'),
                 ('tagdef', self.tag_id),
                 ('tagdef active', None),
                 ('tagdef type', self.typestr),
                 ('tagdef readpolicy', self.readpolicy),
                 ('tagdef writepolicy', self.writepolicy),
                 ('read users', '*') ]
        if owner:
            tags.append( ('owner', owner) )
        if self.multivalue:
            self.multivalue = downcast_value('boolean', self.multivalue)
            tags.append( ('tagdef multivalue', self.multivalue) )
        else:
            tags.append( ('tagdef multivalue', False) )
        if self.is_unique:
            self.is_unique = downcast_value('boolean', self.is_unique)
            tags.append( ('tagdef unique', self.is_unique) )
        else:
            tags.append( ('tagdef unique', False) )

        for tag, value in tags:
            self.set_tag(subject, self.globals['tagdefsdict'][tag], value)

        tagdef = web.Storage([ (Application.tagdef_listas.get(key, key), value) for key, value in tags ])
        tagdef.id = newid
        if owner == None:
            tagdef.owner = None
        tagdef.multivalue = self.multivalue
        tagdef.unique = self.is_unique
        
        self.deploy_tagdef(tagdef)

    def deploy_tagdef(self, tagdef):
        tabledef = "CREATE TABLE %s" % (self.wraptag(tagdef.tagname))
        tabledef += " ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE"
        indexdef = ''

        type = self.globals['typesdict'].get(tagdef.typestr, None)
        if type == None:
            raise Conflict(self, 'Referenced type "%s" is not defined.' % tagdef.typestr)

        dbtype = type['typedef dbtype']
        if dbtype != '':
            tabledef += ", value %s" % dbtype
            if dbtype == 'text':
                tabledef += " DEFAULT ''"
            elif dbtype == 'boolean':
                tabledef += ' DEFAULT False'
            tabledef += ' NOT NULL'

            if tagdef.unique:
                tabledef += ' UNIQUE'

            tagref = type['typedef tagref']
                
            if tagref:
                if tagref == 'name':
                    tagref = 'latest with name' # need to remap to unique variant

                referenced_tagdef = self.globals['tagdefsdict'].get(tagref, None)

                if referenced_tagdef == None:
                    raise Conflict(self, 'Referenced tag "%s" not found.' % tagref)

                if referenced_tagdef.unique and referenced_tagdef.typestr != 'empty':
                    tabledef += ' REFERENCES %s (value) ON DELETE CASCADE' % self.wraptag(tagref)
                
            if not tagdef.multivalue:
                tabledef += ", UNIQUE(subject)"
            else:
                tabledef += ", UNIQUE(subject, value)"
                
            indexdef = 'CREATE INDEX %s' % (self.wraptag(tagdef.tagname, '_value_idx'))
            indexdef += ' ON %s' % (self.wraptag(tagdef.tagname))
            indexdef += ' (value)'
        else:
            tabledef += ', UNIQUE(subject)'
            
        tabledef += " )"
        #web.debug(tabledef)
        self.dbquery(tabledef)
        if indexdef:
            self.dbquery(indexdef)

    def delete_tagdef(self, tagdef):
        self.undeploy_tagdef(tagdef)
        tagdef.name = None
        tagdef.version = None
        self.delete_file( tagdef, allow_tagdef=True)

    def undeploy_tagdef(self, tagdef):
        self.dbquery('DROP TABLE %s' % (self.wraptag(tagdef.tagname)))

    def select_tag_noauthn(self, subject, tagdef, value=None):
        wheres = []
        vars = dict()
        if subject:
            # subject can be set to None by caller to search all subjects
            vars['subject'] = subject.id
            wheres.append('subject = $subject')
            
        if tagdef.typestr != 'empty' and value != None:
            if value == '':
                wheres.append('tag.value IS NULL')
            else:
                vars['value'] = value
                wheres.append('tag.value = $value')

        query = 'SELECT tag.* FROM %s AS tag' % self.wraptag(tagdef.tagname)

        if wheres:
            query += ' WHERE ' + ' AND '.join(wheres)

        if tagdef.typestr != 'empty':
            query += '  ORDER BY value'

        #web.debug(query, vars)
        return self.dbquery(query, vars=vars)

    def select_tag(self, subject, tagdef, value=None):
        # subject would not be found if read of subject is not OK
        if tagdef.readok == False or (tagdef.readok == None and not self.test_tag_authz('read', subject, tagdef)):
            raise Forbidden(self, 'read access to /tags/%s(%s)' % (self.subject2identifiers(subject)[0], tagdef.tagname))
        return self.select_tag_noauthn(subject, tagdef, value)

    def gettagvals(self, subject, tagdef):
        results = self.select_tag(subject, tagdef)
        values = [ ]
        for result in results:
            try:
                value = result.value
                if value == None:
                    value = ''
                values.append(value)
            except:
                pass
        return values

    def select_filetags_noauthn(self, subject=None, tagname=None):
        wheres = []
        vars = dict()
        if subject:
            vars['id'] = subject.id
            wheres.append("subject = $id")

        if tagname:
            vars['tagname'] = tagname
            wheres.append("tagname = $tagname")
        
        wheres = ' AND '.join(wheres)
        if wheres:
            wheres = " WHERE " + wheres
            
        query = 'SELECT subject AS id, tagname FROM subjecttags' \
                + wheres \
                + " ORDER BY id, tagname"
        
        #web.debug(query, vars)
        return self.dbquery(query, vars=vars)

    def set_tag_lastmodified(self, subject, tagdef):
        if tagdef.tagname in [ 'tag last modified', 'tag last modified txid', 'subject last tagged', 'subject last tagged txid' ]:
            # don't recursively track tags we generate internally
            return

        def insert_or_update(table, vars):
            self.dbquery('LOCK TABLE %s IN EXCLUSIVE MODE' % table)
            results = self.dbquery('SELECT value FROM %s WHERE subject = $subject'  % table, vars=vars)

            if len(results) > 0:
                value = results[0].value
                if value < vars['now']:
                    self.dbquery('UPDATE %s SET value = $now WHERE subject = $subject' % table, vars=vars)
                    #web.debug('set %s from %s to %s' % (table, value, vars['now']))
                elif value == vars['now']:
                    pass
                else:
                    pass
                    #web.debug('refusing to set %s from %s to %s' % (table, value, vars['now']))
            else:
                self.dbquery('INSERT INTO %s (subject, value) VALUES ($subject, $now)' % table, vars=vars)
                #web.debug('set %s to %s' % (table, vars['now']))

        now = datetime.datetime.now(pytz.timezone('UTC'))
        txid = self.dbquery('SELECT txid_current() AS txid')[0].txid

        insert_or_update(self.wraptag('tag last modified'), dict(subject=tagdef.id, now=now))
        insert_or_update(self.wraptag('tag last modified txid'), dict(subject=tagdef.id, now=txid))

        if subject != None:
            insert_or_update(self.wraptag('subject last tagged'), dict(subject=subject.id, now=now))
            insert_or_update(self.wraptag('subject last tagged txid'), dict(subject=subject.id, now=txid))

    def delete_tag(self, subject, tagdef, value=None):
        wheres = ['tag.subject = $id']

        if value or value == '':
            wheres.append('tag.value = $value')
        if wheres:
            wheres = ' WHERE ' + ' AND '.join(wheres)
        else:
            wheres = ''

        # special handling only if ending period of deferred policy remapping
        fire_doPolicyRule = False
        if tagdef.tagname == 'incomplete':
            results = self.select_tag_noauthn(subject, tagdef)
            if len(results) > 0:
                fire_doPolicyRule = True

        query = 'DELETE FROM %s AS tag' % self.wraptag(tagdef.tagname) + wheres + ' RETURNING subject'
        vars=dict(id=subject.id, value=value, tagname=tagdef.tagname)
        deleted = self.dbquery(query, vars=vars)
        if len(deleted) > 0:
            self.set_tag_lastmodified(subject, tagdef)

            results = self.select_tag_noauthn(subject, tagdef)
            if len(results) == 0:
                query = 'DELETE FROM subjecttags AS tag WHERE subject = $id AND tagname = $tagname'
                self.dbquery(query, vars=vars)

            # update in-memory representation too for caller's sake
            if tagdef.multivalue:
                subject[tagdef.tagname] = [ res.value for res in self.select_tag_noauthn(subject, tagdef) ]
            elif tagdef.typestr != 'empty':
                results = self.select_tag_noauthn(subject, tagdef)
                if len(results) > 0:
                    subject[tagdef.tagname] = results[0].value
                else:
                    subject[tagdef.tagname] = None
            else:
                subject[tagdef.tagname ] = False

            if fire_doPolicyRule:
                self.doPolicyRule(subject)

    def set_tag(self, subject, tagdef, value=None):
        typedef = self.globals['typesdict'].get(tagdef.typestr, None)
        if typedef == None:
            raise Conflict(self, 'The tag definition references a field type "%s" which is not defined!' % typestr)
        dbtype = typedef['typedef dbtype']

        if tagdef.writepolicy != 'system':
            # only run extra validation on user-provided values...
            validator = Application.tagnameValidators.get(tagdef.tagname)
            if validator:
                validator(self, value, tagdef, subject)

            validator = Application.tagtypeValidators.get(typedef.typedef)
            if validator:
                results = validator(self, value, tagdef, subject)
                if results != None:
                    # validator converted user-supplied value to internal form to use instead
                    value = results

            def convert(v):
                try:
                    return downcast_value(dbtype, v)
                except:
                    raise BadRequest(self, data='The value "%s" cannot be converted to stored type "%s".' % (v, dbtype))

            if value:
                if type(value) in [ list, set ]:
                    value = [ convert(v) for v in value ]
                else:
                    value = convert(value)

        if type(value) in [ list, set ]:
            # validatator generated a set of values, recursively try to set these instead
            for val in value:
                self.set_tag(subject, tagdef, val)
            return

        if tagdef.unique:
            results = self.select_tag_noauthn(None, tagdef, value)
            if len(results) > 0 and results[0].subject != subject.id:
                if tagdef.typestr != 'empty':
                    raise Conflict(self, 'Tag "%s" is defined as unique and value "%s" is already bound to another subject.' % (tagdef.tagname, value))
                else:
                    raise Conflict(self, 'Tag "%s" is defined as unique is already bound to another subject.' % (tagdef.tagname))

        # check whether triple already exists
        results = self.select_tag_noauthn(subject, tagdef, value)
        if len(results) > 0:
            return

        vars = dict(subject=subject.id, value=value, tagname=tagdef.tagname)

        if not tagdef.multivalue:
            # check pre-conditions before inserting triple
            if dbtype == '':
                # subject must not be tagged yet or we wouldn't be here...
                pass
            else:
                if value != None:
                    query = 'UPDATE %s' % self.wraptag(tagdef.tagname) \
                            + ' SET value = $value' \
                            + ' WHERE subject = $subject'
                    if tagdef.tagname == 'modified' and subject.has_key('modified'):
                        # optimize for concurrent file access
                        query += ' AND value < $value'
                    query +=  ' RETURNING value'
                else:
                    query = 'UPDATE %s' % self.wraptag(tagdef.tagname) \
                            + ' SET value = DEFAULT' \
                            + ' WHERE subject = $subject' \
                            + ' RETURNING value'

                results = self.dbquery(query, vars=vars)

                if len(results) > 0 or (tagdef.tagname == 'modified' and subject.has_key('modified')):
                    # (subject, value) updated in place, so we're almost done...
                    self.set_tag_lastmodified(subject, tagdef)
                    return

        # if we get here, insertion is needed
        if dbtype != '' and value != None:
            query = 'INSERT INTO %s' % self.wraptag(tagdef.tagname) \
                    + ' (subject, value) VALUES ($subject, $value)'
        else:
            # insert untyped or typed w/ default value...
            query = 'INSERT INTO %s' % self.wraptag(tagdef.tagname) \
                    + ' (subject) VALUES ($subject)'

        self.dbquery(query, vars=vars)

        # update in-memory representation too for caller's sake
        if tagdef.multivalue:
            subject[tagdef.tagname] = [ res.value for res in self.select_tag_noauthn(subject, tagdef) ]
        elif tagdef.typestr != 'empty':
            subject[tagdef.tagname] = self.select_tag_noauthn(subject, tagdef)[0].value
        else:
            subject[tagdef.tagname] = True
        
        results = self.select_filetags_noauthn(subject, tagdef.tagname)
        if len(results) == 0:
            results = self.dbquery("INSERT INTO subjecttags (subject, tagname) VALUES ($subject, $tagname)", vars=vars)
        else:
            # may already be reverse-indexed in multivalue case
            pass

        self.set_tag_lastmodified(subject, tagdef)
        

    def select_next_transmit_number(self):
        query = "SELECT NEXTVAL ('transmitnumber')"
        vars = dict()
        # now, as we can set manually dataset names, make sure the new generated name is unique
        while True:
            result = self.dbquery(query)
            name = str(result[0].nextval).rjust(9, '0')
            vars['value'] = name
            res = self.dbquery('SELECT * FROM "_name" WHERE value = $value', vars)
            if len(res) == 0:
                return name

    def select_next_key_number(self):
        query = "SELECT NEXTVAL ('keygenerator')"
        vars = dict()
        # now, as we can set manually dataset names, make sure the new generated name is unique
        while True:
            result = self.dbquery(query)
            value = str(result[0].nextval).rjust(9, '0')
            vars['value'] = value
            res = self.dbquery('SELECT * FROM "_key" WHERE value = $value', vars)
            if len(res) == 0:
                return value

    def build_files_by_predlist_path(self, path=None, versions='latest', limit=None, enforce_read_authz=True, tagdefs=None, typedefs=None, vprefix='', listas={}, values=None, offset=None):
        """Build SQL query expression and values map implementing path query.

           'path = []'    equivalent to path = [ ([], [], []) ]

           'path[-1]'     describes final resulting type/structure... 
                          of form [ web.storage{'id'=N, 'list tag 1'=val, 'list tag 2'=[val...]}... ]

           'path[0:-1]'   contextually constraints set of subjects which can be matched by path[-1]

           'path'         defaults to self.path if not supplied
           'tagdefs'      defaults to self.globals['tagdefsdict'] if not supplied
           'typedefs'     defaults to self.globals['typesdict'] if not supplied
           'listas'       provides an optional relabeling of list tags (projected result attributes)

           Optional args 'values'used for recursive calls, not client calls.
        """
        if path == None:
            path = self.path

        if not path:
            path = [ ( [], [], [] ) ]

        if tagdefs == None:
            tagdefs = self.globals['tagdefsdict']

        if typedefs == None:
            typedefs = self.globals['typesdict']

        if listas == None:
            listas = dict()

        if not values:
            values = Values()

        roles = [ r for r in self.authn.roles ]
        roles.append('*')
        roles = set(roles)
        rolekeys = ','.join([ '$%s' % values.add(r) for r in roles ])

        prohibited = set(listas.itervalues()).intersection(set(['id', 'readok', 'writeok', 'txid', 'owner', 'dtype']))
        if len(prohibited) > 0:
            raise BadRequest(self, 'Use of %s as list tag alias is prohibited.' % ', '.join(['"%s"' % t for t in prohibited]))

        prohibited = set(listas.iterkeys()).intersection(set(['id', 'readok', 'writeok', 'txid', 'owner', 'dtype']))
        if len(prohibited) > 0:
            raise BadRequest(self, 'Aliasing of %s is prohibited.' % ', '.join(['"%s"' % t for t in prohibited]))

        rangemode = self.queryopts.get('range', None)
        if rangemode not in [ 'values', 'count', 'values<', 'values>' ]:
            rangemode = None

        def mergepreds(predlist):
            """Reorganize predlist into a map keyed by tag, listing all preds that constrain each tag.

               Resulting map has a key for each tag referenced in a
               predicate. The keyed list of predicates should then be
               compiled into a conjunction of value constraints on
               that tag.
            """
            pd = dict()
            for pred in predlist:
                vals = pred.vals
                if type(vals) == list:
                    vals = [ v for v in pred.vals ]
                    vals.sort()

                pred = web.Storage(tag=pred.tag, op=pred.op, vals=vals)

                tagdef = tagdefs.get(pred.tag, None)
                if tagdef == None:
                    #raise KeyError()
                    raise Conflict(self, 'Tagdef "%s" not defined on this server.' % pred.tag)

                pl = pd.get(pred.tag, [])
                pd[pred.tag] = pl
                pl.append(pred)

            for tag, preds in pd.items():
                preds.sort(key=lambda p: (p.op, p.vals))

            return pd
        
        def tag_query(tagdef, preds, values, final=True, tprefix='_', spred=False):
            """Compile preds for one tag into a query fetching all satisfactory triples.

               Returns (tagdef, querystring, subject_wheres)
                 -- querystring is compiled query
                 -- subject_wheres is list of additional WHERE
                    clauses, which caller should apply for subject
                    queries; when non-empty, caller should use LEFT
                    OUTER JOIN to combine querystring with resources
                    table.

               final=False uses template: "q"
               final=True  uses template: "( q ) AS alias"  and array_agg of multivalue tags

               normal query templates:
                   SELECT subject FROM "_%(tagname)s"
                   SELECT subject, subject AS value FROM resources [WHERE subject ...]
                   SELECT subject, value FROM "_%(tagname)s" [WHERE value ...]
                   SELECT subject, value FROM "_%(tagname)s" [JOIN (SELECT subject FROM "_%(tagname)s" WHERE value ...) USING subject]...
                   SELECT subject, value FROM "_%(tagname)s" [JOIN (SELECT subject FROM "_%(tagname)s" WHERE value ...) USING subject]...
                   SELECT subject, array_agg(value) AS value FROM "_%(tagname)s" [JOIN (SELECT subject FROM "_%(tagname)s" WHERE value ...) USING subject]...

               values is used to produce a query parameter mapping
               with keys unique across a set of compiled queries.
            """
            subject_wheres = []

            m = dict(value='', where='', group='', table=wraptag(tagdef.tagname), alias=wraptag(tagdef.tagname, prefix=tprefix))
            wheres = []

            valcol = '%s.value'  % wraptag(tagdef.tagname)
            if tagdef.tagname == 'id':
                m['table'] = 'resources'
                m['value'] = ', subject AS value'
                valcol = 'subject'
            elif tagdef.multivalue and final:
                m['value'] = ', array_agg(%s.value) AS value' % wraptag(tagdef.tagname)
                m['group'] = 'GROUP BY subject'
            elif tagdef.typestr != 'empty':
                m['value'] = ', %s.value AS value' % wraptag(tagdef.tagname)

            used_not_op = False
            used_other_op = False
            for pred in preds:
                if pred.op == ':absent:':
                    used_not_op = True
                else:
                    used_other_op = True

                if pred.op == 'IN':
                    wheres.append( '%s IN (%s)' % (valcol, pred.vals) )
                elif pred.op != ":absent:" and pred.op and pred.vals:
                    if tagdef.typestr == 'empty':
                        raise Conflict(self, 'Operator "%s" not supported for tag "%s".' % (pred.op, tagdef.tagname))

                    def vq_compile(ast):
                        """Compile a querypath supplied as a predicate value into a SQL sub-query."""
                        path = [ x for x in ast.path ]
                        spreds, lpreds, otags = path[-1]
                        lpreds = [ x for x in lpreds ]
                        
                        projtag = tagdef.tagref
                        if projtag:
                            lpreds.append( web.Storage(tag=projtag, op=None, vals=[]) )
                        elif tagdef.tagname == 'id':
                            projtag = 'id'
                        else:
                            raise BadRequest(self, 'Subquery as predicate value not supported for tag "%s".' % tagdef.tagname)
                        
                        path[-1] = (spreds, lpreds, [])
                        vq, vqvalues = self.build_files_by_predlist_path(path, versions=versions, values=values)
                        return 'SELECT %s FROM (%s) AS sq' % (wraptag(projtag, prefix=''), vq)
                        
                    vkeys = [ values.add(v, tagdef.dbtype, range_extensions=True) for v in pred.vals if not hasattr(v, 'is_subquery') ]
                    vqueries = [ vq_compile(vq) for vq in pred.vals if hasattr(v, 'is_subquery') ]
                    constants = [ '($%s::%s)' % (v, tagdef.dbtype) for v in vkeys if type(v) != tuple ]
                    bounds = [ '($%s::%s, $%s::%s)' % (v[0], tagdef.dbtype, v[1], tagdef.dbtype) for v in vkeys if type(v) == tuple ]
                    clauses = []
                    if constants:
                        constants = ', '.join(constants)
                        clauses.append( '(SELECT bool_or(%s %s t.x) FROM (VALUES %s) AS t (x))'
                                        %  (valcol, Application.opsDB[pred.op], constants) )

                    if bounds:
                        bounds = ', '.join(bounds)
                        if pred.op in [ '=', '!=' ]:
                            clauses.append( '(SELECT bool_or(%s %s BETWEEN t.lower AND t.upper) FROM (VALUES %s) AS t (lower, upper))'
                                            % (valcol, { '=': '', '!=': 'NOT' }[pred.op], bounds) )
                        else:
                            raise Conflict(self, 'Bounded value ranges are not supported for operator %s.' % pred.op)
                    
                    if vqueries:
                        vqueries = ' UNION '.join(vqueries)
                        clauses.append( '(SELECT bool_or(%s %s t.x) FROM (%s) AS t (x))'
                                        % (valcol, Application.opsDB[pred.op], vqueries) )
                    wheres.append( ' OR '.join(clauses) )

            if used_not_op:
                # we need to enforce absence of (readable) triples
                subject_wheres.append('%s.subject IS NULL' % wraptag(tagdef.tagname, prefix=tprefix))
                if used_other_op:
                    # we also need to enforce presence of (readable) triples! (will always be False)
                    subject_wheres.append('%s.subject IS NOT NULL' % wraptag(tagdef.tagname, prefix=tprefix))
                    
            if enforce_read_authz:
                if tagdef.readok == False:
                    wheres = [ 'False' ]
                elif tagdef.readpolicy == 'subjectowner':
                    m['table'] += ' LEFT OUTER JOIN %s o USING (subject)' % wraptag('owner')
                    wheres.append( 'o.value IN (%s)' % rolekeys )

            w = ' AND '.join([ '(%s)' % w for w in wheres ])
            if w:
                m['where'] = 'WHERE ' + w

            if tagdef.typestr != 'empty':
                if tagdef.multivalue and wheres and spred:
                    # multivalue spred requires SUBJECT to match all preds, possibly using different triples for each match
                    m['where'] = ''
                    tables = [ m['table'] ]
                    for i in range(0, len(wheres)):
                        tables.append( 'JOIN (SELECT subject FROM %s WHERE %s GROUP BY subject) AS %s USING (subject)'
                                       % (wraptag(tagdef.tagname), wheres[i], wraptag(tagdef.tagname, prefix='w%d' % i)) )
                    m['table'] = ' '.join(tables)

                # single value or multivalue lpred requires VALUE to match all preds
                q = 'SELECT subject%(value)s FROM %(table)s %(where)s %(group)s'
            else:
                q = 'SELECT subject FROM %(table)s %(where)s'
            
            if final:
                q = '(' + q + ') AS %(alias)s'

            return (q % m, subject_wheres)

        def elem_query(spreds, lpreds, values, final=True):
            """Compile a query finding subjects by spreds and projecting by lpreds.

               final=True means projection is one column per ltag.
               final=False means projection is a single-column UNION of all ltags.

               values is used to produce a query parameter mapping
               with keys unique across a set of compiled queries.
            """
            spreds = mergepreds(spreds)
            lpreds = mergepreds(lpreds)

            subject_wheres = []

            for tag, preds in lpreds.items():
                if tag == 'id':
                    if len([ p for p in preds if p.op]) != 0:
                        raise BadRequest(self, 'Tag "id" cannot be filtered in a list-predicate.')
                    if not final or rangemode == None:
                        del lpreds[tag]

            selects = []
            inner = []
            outer = []

            versions_test_added = []
            if versions == 'latest':
                subject_wheres.append( '%s.subject IS NULL OR %s.subject IS NOT NULL'
                                       % (wraptag('name', prefix='s_'), wraptag('latest with name', prefix='s_')) )
                for tag in ['name', 'latest with name']:
                    if not spreds.has_key(tag):
                        spreds[tag] = []
                        versions_test_added.append(tag)

            for tag, preds in spreds.items():
                sq, swheres = tag_query(tagdefs[tag], preds, values, tprefix='s_', spred=True)
                if swheres or tag in versions_test_added:
                    outer.append(sq)
                    subject_wheres.extend(swheres)
                else:
                    inner.append(sq)

            if enforce_read_authz:
                inner += [ '(SELECT DISTINCT subject from _owner AS o WHERE o.value IN (%(rolekeys)s)'
                           ' UNION SELECT DISTINCT subject from "_read users" AS ru WHERE ru.value IN (%(rolekeys)s)) AS r'
                           % dict(rolekeys='%s' % rolekeys) ]

                outer += [ '"_subject last tagged txid" t',
                           '"_owner" o',
                           '(SELECT DISTINCT subject FROM "_write users" WHERE value IN (%(rolekeys)s)) AS wu'
                           % dict(rolekeys='%s' % rolekeys) ]

                if final and rangemode == None:
                    selects += [ 'r.subject AS id',
                                 'True AS readok',
                                 'wu.subject IS NOT NULL OR o.value IN (%(rolekeys)s) AS writeok' % dict(rolekeys='%s' % rolekeys),
                                 'o.value AS owner',
                                 't.value AS txid' ]
            else:
                inner += [ 'resources AS r' ]

                outer += [ '"_subject last tagged txid" t',
                           '"_owner" o',
                           '(SELECT DISTINCT subject FROM "_read users" WHERE value IN (%(rolekeys)s)) AS ru' % dict(rolekeys='%s' % rolekeys),
                           '(SELECT DISTINCT subject FROM "_write users" WHERE value IN (%(rolekeys)s)) AS wu' % dict(rolekeys='%s' % rolekeys) ]
                if final and rangemode == None:
                    selects += [ 'r.subject AS id',
                                 'ru.subject IS NOT NULL OR o.value IN (%(rolekeys)s) AS readok' % dict(rolekeys='%s' % rolekeys),
                                 'wu.subject IS NOT NULL OR o.value IN (%(rolekeys)s) AS writeok' % dict(rolekeys='%s' % rolekeys),
                                 'o.value AS owner',
                                 't.value AS txid' ]

            finals = []
            for tag, preds in lpreds.items():
                td = tagdefs[tag]
                if rangemode and final:
                    if len([ p for p in preds if p.op]) > 0:
                        raise BadRequest(self, 'Operators not supported in rangemode list predicates.')
                    if td.typestr != 'empty':
                        # find active value range for given tag
                        if td.tagname == 'id':
                            range_column = 'resources.subject'
                            range_table = 'resources'
                        else:
                            range_column = wraptag(td.tagname) + '.value'
                            range_table = wraptag(td.tagname) + ' JOIN resources USING (subject)'
                    else:
                        # pretend empty tags have binary range True, False
                        range_column = 't.x'
                        range_table = '(VALUES (True), (False)) AS t (x)'

                else:
                    if tag == 'owner':
                        # owner is restricted, since it MUST appear unfiltered in all results
                        if len(set([p.op for p in preds]).difference(set([None]))) > 0:
                            raise Conflict(self, 'The tag "owner" cannot be filtered in projection list predicates.')
                        # skip this iteration since it's already in the base results
                        continue
                    elif spreds.has_key(tag) and len(preds) == 0 and not tagdefs[tag].multivalue and final and rangemode == None:
                        # this projection does not further filter triples relative to the spred so optimize it away
                        td = tagdefs[tag]
                        lq = None
                    else:
                        lq, swheres = tag_query(td, preds, values, final, tprefix='l_')
                        if swheres:
                            raise BadRequest(self, 'Operator ":absent:" not supported in projection list predicates.')

                if final:
                    if rangemode == None:
                        # returning triple values per subject
                        if lq:
                            outer.append(lq)
                            tprefix = 'l_'
                        else:
                            tprefix = 's_'
                        if td.typestr != 'empty':
                            selects.append('%s.value AS %s' % (wraptag(td.tagname, prefix=tprefix), wraptag(listas.get(td.tagname, td.tagname), prefix='')))
                        else:
                            selects.append('%s.subject IS NOT NULL AS %s' % (wraptag(td.tagname, prefix=tprefix), wraptag(listas.get(td.tagname, td.tagname), prefix='')))
                    elif rangemode == 'values':
                        # returning distinct values across all subjects
                        selects.append('(SELECT array_agg(DISTINCT %s) FROM %s) AS %s'
                                       % (range_column, range_table, wraptag(listas.get(td.tagname, td.tagname), prefix='')))
                    elif rangemode == 'count':
                        # returning count of distinct values across all subjects
                        selects.append('(SELECT count(DISTINCT %s) FROM %s) AS %s'
                                       % (range_column, range_table, wraptag(listas.get(td.tagname, td.tagname), prefix='')))
                    else:
                        # returning (in)frequent values
                        if rangemode[-1] == '<':
                            freqorder = 'ASC'
                        else:
                            freqorder = 'DESC'
                        selects.append('(SELECT array_agg(value) '
                                        'FROM (SELECT %(column)s AS value, count(%(column)s) AS count '
                                              'FROM %(table)s '
                                              'GROUP BY %(column)s '
                                              'ORDER BY count %(order)s, value '
                                              '%(limit)s) AS t) '
                                        'AS %(alias)s'
                                       % dict(column=range_column,
                                              table=range_table,
                                              order=freqorder,
                                              limit=({ True: 'LIMIT %d' % limit, False: ''}[limit != None]),
                                              alias=wraptag(listas.get(td.tagname, td.tagname), prefix='')))
                        
                else:
                    finals.append(lq)

            if not final:
                outer.append( '(%s) AS context' % ' UNION '.join([ sq for sq in finals ]) )
                selects.append('context.value AS context')

            if subject_wheres:
                where = 'WHERE ' + ' AND '.join([ '(%s)' % w for w in subject_wheres ])
            else:
                where = ''

            if rangemode == None or not final:
                q = ('SELECT %(selects)s FROM %(tables)s %(where)s' 
                     % dict(selects=', '.join([ s for s in selects ]),
                            tables=' LEFT OUTER JOIN ' \
                            .join([ ' JOIN '.join(inner[0:1] + [ '%s USING (subject)' % i for i in inner[1:] ]) ]
                                  + [ '%s USING (subject)' % o for o in outer ]),
                            where=where))
            else:
                q = ('WITH resources AS ( SELECT r.subject FROM %(tables)s %(where)s ) SELECT %(selects)s' 
                     % dict(selects=', '.join([ s for s in selects ]),
                            tables=' LEFT OUTER JOIN ' \
                            .join([ ' JOIN '.join(inner[0:1] + [ '%s USING (subject)' % i for i in inner[1:] ]) ]
                                  + [ '%s USING (subject)' % o for o in outer ]),
                            where=where))
            
            return q

        cq = None
        order = None
        for i in range(0, len(path)):
            spreds, lpreds, otags = path[i]
            if i > 0:
                cpreds = path[i-1][1]
                tagtypes = set([ tagdefs[pred.tag].typestr for pred in cpreds ])
                tagrefs = set([ typedefs[t]['typedef tagref'] for t in tagtypes ])
                if len(tagrefs) > 1:
                    raise BadRequest(self, 'Path element %d has %d disjoint projection tag-references when at most 1 is supported.' % (i-1, len(tagrefs)))
                elif len(tagrefs) == 1:
                    context_attr = tagrefs.pop()
                elif len(tagtypes) == 1:
                    context_attr = dict(text='name', id='id')[tagtypes.pop()]
                else:
                    raise BadRequest(self, 'Path element %d has %d disjoint projection types when exactly 1 is required' % (i-1, len(tagtypes)))
                spreds = [ p for p in spreds ]
                spreds.append( web.storage(tag=context_attr, op='IN', vals=cq) )

            if i == len(path) - 1:
                lpreds = [ p for p in lpreds ]
                if rangemode == None:
                    lpreds.extend([ web.storage(tag=tag, op=None, vals=[]) for tag, dir in otags ])
                    if otags != None and len(otags):
                        order = ' ORDER BY %s' % ', '.join([ '%s %s NULLS LAST' % (wraptag(listas.get(t, t), prefix=''),
                                                                        { ':asc:': 'ASC', ':desc:': 'DESC', None: 'ASC'}[dir])
                                                             for t, dir in otags])

            cq = elem_query(spreds, lpreds, values, i==len(path)-1)

        if order:
            cq += order

        if limit and rangemode == None:
            cq += ' LIMIT %d' % limit

        if offset and rangemode == None:
            cq += ' OFFSET %d' % offset

        def dbquote(s):
            return s.replace("'", "''")
        
        #traceInChunks(cq)
        #web.debug('values', values.pack())

        return (cq, values.pack())


    def build_select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, version=None, qd=0, versions='latest', listas=None, tagdefs=None, typedefs=None, enforce_read_authz=True, limit=None, listpreds=None, vprefix=''):
        """Backwards compatibility interface, pass to general predlist path function."""

        if subjpreds == None:
            subjpreds = self.subjpreds

        if id != None:
            subjpreds.append( web.Storage(tag='id', op='=', vals=[id]) )

        if listpreds == None:
            if listtags == None:
                listtags = [ x for x in self.globals['filelisttags'] ]
            else:
                listtags = [ x for x in listtags ]

            listpreds = [ web.Storage(tag=tag, op=None, vals=[]) for tag in listtags ]
        else:
            listpreds = [ x for x in listpreds ]

        return self.build_files_by_predlist_path(path=[ (subjpreds, listpreds, ordertags) ], versions=versions, limit=limit, enforce_read_authz=enforce_read_authz, tagdefs=tagdefs, typedefs=typedefs, listas=listas)


    def select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, version=None, versions='latest', listas=None, tagdefs=None, typedefs=None, enforce_read_authz=True, limit=None, listpreds=None):

        query, values = self.build_select_files_by_predlist(subjpreds, listtags, ordertags, id=id, version=version, versions=versions, listas=listas, tagdefs=tagdefs, typedefs=typedefs, enforce_read_authz=enforce_read_authz, limit=limit, listpreds=None)

        #web.debug(len(query), query, values)
        #web.debug('%s bytes in query:' % len(query))
        #for string in query.split(','):
        #    web.debug (string)
        #web.debug(values)
        #web.debug('...end query')
        #for r in self.dbquery('EXPLAIN ANALYZE %s' % query, vars=values):
        #    web.debug(r)
        return self.dbquery(query, vars=values)

    def select_files_by_predlist_path(self, path=None, versions='latest', limit=None, enforce_read_authz=True, offset=None):
        #self.txlog('TRACE', value='select_files_by_predlist_path entered')
        query, values = self.build_files_by_predlist_path(path, versions, limit=limit, enforce_read_authz=enforce_read_authz, offset=offset)
        #self.txlog('TRACE', value='select_files_by_predlist_path query built')
        result = self.dbquery(query, values)
        #self.txlog('TRACE', value='select_files_by_predlist_path exiting')
        return result

    def select_predlist_path_txid(self, path=None, versions='latest', limit=None, enforce_read_authz=True):
        """Determine last-modified txid for query path dataset, optionally testing previous txid as shortcut.

           The value prev_txid is trusted to be an accurate value, if it is provided.
        """
        if not path:
            path = [ ( [], [], [] ) ]

        def relevant_tags_txid(path):
            """Find the most recent txid at which any relevant tag was updated.

               This test is a conservative upper bound, taking into
               account result sets which could change due to changes in:

               -- read authz affecting visible result members

               -- tags affecting subject predicate sets

               -- tags affecting list predicate sets

               -- resource addition/deletion affecting unconstrained
                  listings, handled via implicit usage of 'id' virtual
                  tag in this case.

               Unfortunately, adding or removing a subject will always
               advance the txid in practice, because it always effects
               the tag-last-modified time of the 'owner' tag if
               nothing else.
            """
            
            def relevant_tags(path):
                """Find the relevant tags involved in computing a query path result."""
                tags = set(['owner', 'read users', 'latest with name'])
                for elem in path:
                    spreds, lpreds, otags = elem
                    if not spreds:
                        # without tag constraints, we have an implicit result set defined by the resources table a.k.a. 'id' tag
                        tags.add('id')
                    tags.update(set([ p.tag for p in spreds + lpreds ] + [ o[0] for o in otags ]))
                    for vals in [ p.vals for p in (spreds + lpreds) if p.vals ]:
                        for v in vals:
                            if hasattr(v, 'is_subquery'):
                                tags.update(relevant_tags(v.path))
                return tags

            tags = relevant_tags(path)
            #web.debug('relevant tags', tags)
            
            path = [ ( [ web.Storage(tag='tagdef', op='=', vals=[ t for t in tags ]) ],
                       [ web.Storage(tag='tag last modified txid', op=None, vals=[]) ],
                       [] ) ]
            query, values = self.build_files_by_predlist_path(path)
            query = 'SELECT max("tag last modified txid") AS txid FROM (%s) AS sq' % query
            return max(self.dbquery(query, vars=values)[0].txid, self.config['subject last tagged txid'])

        return relevant_tags_txid(path)

    def prepare_path_query(self, path, list_priority=['path', 'list', 'view', 'subject', 'default'], list_prefix=None, extra_tags=[]):
        """Prepare (path, listtags, writetags, limit, versions) from input path, web environment, and input policies.

           list_priority  -- chooses first successful source of listtags

                'path' : use listpreds from path[-1]
                'list' : use 'list' queryopt
                'view' : use view named by 'view' queryopt
                'subject' : use view named by 'default view' tag of subject ... REQUIRES EXTRA QUERY STEP AND SINGLE SUBJECT
                'default' : use 'default' view
                'all' : use all defined tags

           view_list_prefix -- enables consultation of view tags

                '%s list tags' % prefix : for listtags
                '%s list tags write' % prefix : for writetags


           extra_tags  -- tags to add to listpreds of path[-1] without adding to listtags or writetags."""

        if not path:
            path = [ ( [], [], [] ) ]
        else:
            # shallow copy
            path = [ x for x in path ]

        subjpreds, listpreds, ordertags = path[-1]
        
        unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True, subjpreds=subjpreds)
        if unique == False:
            versions = 'latest'
        else:
            # unique is True or None
            versions = 'any'

        versions = self.queryopts.get('versions', versions)
        if versions not in [ 'latest', 'any' ]:
            versions = 'latest'

        def wrap_results(listtags=None, listpreds=None, writetags=[], ordered=False):
            # build full results tuple from derived listtags or listpreds, reordering a bit if ordered=False
            if listpreds:
                have_tags = set([ p.tag for p in listpreds ])
            else:
                if not listtags:
                    listtags = [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() ]
                listpreds = [ web.Storage(tag=tag, op=None, vals=[]) for tag in listtags ]
                have_tags = set(listtags)

            listpreds += [ web.Storage(tag=tag, op=None, vals=[]) for tag in extra_tags if tag not in have_tags ]
            have_tags.update( set(extra_tags) )

            if not ordered:
                # apply re-ordering hack
                suffix = [ x for x in [ 'base name', 'name', 'id' ] if x in have_tags ]
                listpreds_new = [ p for p in listpreds if p.tag not in suffix ]
                for tag in suffix:
                    listpreds_new += [ p for p in listpreds if p.tag == tag ]
                listpreds = listpreds_new

            listtags = [ p.tag for p in listpreds ]
            path[-1] = ( subjpreds, listpreds, ordertags )

            limit = self.queryopts.get('limit', 'default')
            
            if limit == 'none':
                limit = None
            elif type(limit) == type('text'):
                try:
                    limit = int(limit)
                except:
                    limit = 25

            offset = self.queryopts.get('offset', None)
            if offset:
                try:
                    offset = int(offset)
                except:
                    offset = None

            return (path, listtags, writetags, limit, offset, versions)

        # each source-specific function conditionally derives listpreds only if source is present and valid in the request...

        def derive_from_path():
            # derive from query path's listpreds
            if listpreds:
                return wrap_results(listpreds=listpreds, ordered=True)
            return None

        listname = '%s list tags' % list_prefix
        writename = '%s list tags write' % list_prefix

        def derive_from_listopt():
            # derive from 'list' query opt
            listopt = self.queryopts.get('list')
            if listopt:
                if type(listopt) in [ list, set ]:
                    return wrap_results(listtags=[ x for x in listopt if x ])
                else:
                    return wrap_results(listtags=[ listopt ])
            return None

        def derive_from_view():
            # derive from view named by 'view' list opt
            viewopt = self.queryopts.get('view')
            view = self.select_view(viewopt)
            if viewopt and view:
                return wrap_results(listtags=view.get(listname, []), writetags=view.get(writename, []))
            return None

        def derive_from_default():
            # derive from default view
            default = self.select_view()
            if default:
                return wrap_results(listtags=default.get(listname, []), writetags=default.get(writename, []))
            return None

        def derive_from_subject():
            # derive from first result's default_view tag
            sview = None
            test_path = [ x for x in path ]
            test_path[-1] = (subjpreds, [web.Storage(tag='default view', op=None, vals=[])], [])
            results = self.select_files_by_predlist_path(test_path, versions=versions, limit=1)
            if len(results) > 0:
                subject = results[0]
                sview = self.select_view(subject['default view'])
            if sview:
                listtags = sview.get(listname, [])
                if listtags:
                    return wrap_results(listtags=listtags, writetags=sview.get(writename, []))
            return None

        def derive_from_all():
            # get full list of tags, which is default behavior of wrap_results
            return wrap_results()

        for source in list_priority:
            # dispatch each per-source function in prioritized source list, until we find one that works
            result = dict(path=derive_from_path,
                          list=derive_from_listopt,
                          view=derive_from_view,
                          default=derive_from_default,
                          subject=derive_from_subject,
                          all=derive_from_all).get(source, derive_from_all)()
            if result != None:
                return result

        return derive_from_all()
                          
    # static class fields
    tagnameValidators = { 'owner' : validateRole,
                          'read users' : validateRolePattern,
                          'write users' : validateRolePattern,
                          'modified by' : validateRole,
                          'typedef values' : validateEnumeration,
                          '_cfg_policy remappings' : validatePolicyRule }

    tagtypeValidators = { 'tagname' : validateTagname,
                          'file' : validateFilename,
                          'vfile' : validateVersionedFilename,
                          'id' : validateSubjectQuery }

