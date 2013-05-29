
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
import tempfile
import logging
import subprocess
import itertools
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
import base64
import struct

import json

try:
    import simplejson
    try:
        decodeError = simplejson.JSONDecodeError
    except:
        decodeError = ValueError
except:
    try:
        decodeError = json.JSONDecodeError
    except:
        decodeError = ValueError

from webauthn2 import jsonReader, jsonWriter, jsonFileReader, merge_config, RestHandlerFactory, Context, Manager

json_whitespace = re.compile(r'[ \t\n\r]*')
json_whitespace_str = ' \t\n\r['

def jsonWhitespaceEat(buf, idx):
    return json_whitespace.match(buf, idx).end()

class JSONArrayError (ValueError):

    def __init__(self, msg):
        ValueError.__init__(self, msg)

def make_temporary_file(fname_prefix, dirname, accessmode):
    """
    Create and open temporary file with accessmode.

    /dirname/fname_prefixXXXXXXXX 

    Returns (fp, filename) on success or raises exception on failure.

    """
    count = 0
    limit = 10
    last_ev = IOError('unknown problem creating temporary file with prefix "%s/%s"' % (dirname, fname_prefix))
    filename = None
    while count < limit:

        count = count + 1

        try:
            if not os.path.exists(dirname):
                os.makedirs(dirname, mode=0755)
        except Exception, ev:
            last_ev = ev
            continue

        try:
            fileHandle, filename = tempfile.mkstemp(prefix=fname_prefix, dir=dirname)
        except Exception, ev:
            last_ev = ev
            continue

        try:
            os.close(fileHandle)
        except Exception, ev:
            last_ev = ev
            try:
                os.remove(filename)
            except:
                pass
            continue

        try:
            f = open(filename, accessmode, 0)
            return (f, filename)
        except Exception, ev:
            last_ev = ev
            try:
                os.remove(filename)
            except:
                pass
 
    raise last_ev

def yieldBytes(f, first, last, chunkbytes):
    """Helper function yields range of file."""
    f.seek(first, 0)  # first from beginning (os.SEEK_SET)
    byte = first
    while byte <= last:
        readbytes = min(chunkbytes, last - byte + 1)
        buf = f.read(readbytes)
        rlen = len(buf)
        byte += rlen
        yield buf
        if rlen < readbytes:
            # undersized read means file got shorter (possible w/ concurrent truncates)
            web.debug('tagfiler.dataserv_app.yieldBytes: short read to %d instead of %d bytes!' % (byte, last))
            # compensate as if the file has a hole, since it is too late to signal an error now
            byte = rlen
            yield bytearray(readbytes - rlen)
            
def jsonArrayFileReader(f):
    """Iterate over elements in JSON array document.

       Input stream must have a JSON array as outermost structure.

       throws JSONArrayError if input doesn't parse properly.
    """
    max_read = 1024 * 1024

    # read double buffer the first time
    buf = f.read(max_read * 2)
    input_done = len(buf) < (max_read * 2)

    pos = jsonWhitespaceEat(buf, 0)

    if pos == len(buf) or buf[pos] != '[':
        raise JSONArrayError('input does not contain JSON array')

    # eat the '[' starting the array
    pos += 1

    try:
        decoder = simplejson.JSONDecoder()
    except:
        decoder = json.JSONDecoder()

    while True:
        try:
            # parse and yield the next array element
            pos = jsonWhitespaceEat(buf, pos)
            elem, pos = decoder.raw_decode(buf, pos)
            yield elem

            # read more input if position has entered max_read guard zone
            if pos >= max_read and not input_done:
                buf2 = f.read(max_read)
                input_done = len(buf2) < max_read
                buf = buf[pos:] + buf2
                pos = 0

            # test the boundary condition
            pos = jsonWhitespaceEat(buf, pos)
            if pos == len(buf):
                raise JSONArrayError('input JSON array incomplete')
            elif buf[pos] == ',':
                # eat the ',' between elements and continue
                pos += 1
            elif buf[pos] == ']':
                # we're done processing the array
                break
            else:
                raise JSONArrayError('input JSON array invalid')

        except decodeError:
            raise JSONArrayError('input JSON array invalid')


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

global_env = merge_config(jsonFileName='tagfiler-config.json', 
                          built_ins={"db": "tagfiler", 
                                     "dbn": "postgres", 
                                     "dbmaxconnections": 8,
                                     "chunk bytes": 1048576,
                                     'file write users': [],
                                     'policy remappings': [],
                                     'tagdef write users': []
                                     }
                          )

webauthn2_config = global_env.get('webauthn2', dict(web_cookie_name='tagfiler'))
webauthn2_config.update(dict(web_cookie_path='/tagfiler'))

webauthn2_manager = Manager(overrides=webauthn2_config)
webauthn2_handler_factory = RestHandlerFactory(manager=webauthn2_manager)

cluster_threshold = 1000

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
    
    elif dbtype in [ 'text', 'tsword' ]:
        value = '%s' % value
        if value.find('\00') >= 0:
            raise ValueError('Null bytes not allowed in text value "%s"' % value)
        if dbtype == 'tsword':
            for c in [ '|', '&', '!', '(', ')', ':', ' ' ]:
                if value.find(c) >= 0:
                    raise ValueError('Character "%s" not allowed in text search words' % c)
        
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
                # these casts to float work because the regexp above only matches decimal digits
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

                # these casts to float work because the regexp only matches decimal digits
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
        try:
            value = int(value)
        except:
            raise ValueError('Value %s cannot be coerced to integer' % str(value))

    elif dbtype == 'float8':
        try:
            value = float(value)
        except:
            raise ValueError('Value %s cannot be coerced to floating point' % str(value))

    elif dbtype in [ 'date', 'timestamptz' ]:
        try:
            if value == 'now':
                value = datetime.datetime.now(pytz.timezone('UTC'))
            elif type(value) in [ str, unicode ]:
                value = dateutil.parser.parse(value)
        except:
            raise ValueError('Value %s cannot be coerced to %s' % (value, dbtype))
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
    
class Values (object):
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

class DbCache (object):
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
                              + ' WHERE subject IN (SELECT subject FROM "_tags present" WHERE value = $idtag)'
                              + ' UNION ALL '
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

class PerUserDbCache (object):

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

tagdef_cache = PerUserDbCache('tagdef', 'tagname')
view_cache = PerUserDbCache('view')

def wraptag(tagname, suffix='', prefix='_'):
    return '"' + prefix + tagname.replace('"','""') + suffix + '"'

def wrapval(value, dbtype=None, range_extensions=False):
    if value == None:
        return 'NULL'
    
    if dbtype:
        value = downcast_value(dbtype, value, range_extensions)

    if type(value) == tuple:
        return ( '%s' % wrapval(value[0], dbtype),
                 '%s' % wrapval(value[1], dbtype) )
    if dbtype == None:
        value = downcast_value('text', value)
    else:
        value = '%s' % value

    if dbtype in [ 'boolean', 'int8', 'float8' ]:
        return '%s' % value
    else:
        return "'%s'" % value.replace("'", "''").replace("%", "%%").replace("$", "$$")
    

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

def make_filter(allowed):
    allchars = string.maketrans('', '')
    delchars = ''.join([c for c in allchars if c not in allowed])
    return lambda s, a=allchars, d=delchars: type(s) == str and s.translate(a,d) or type(s) == unicode and s.translate(dict([ (ord(c), None) for c in d])) or str(s).translate(a, d)

idquote = make_filter(string.letters + string.digits + '_-:.' )

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
                                                       web.ctx.ip, ast and ast.context and ast.context.client and u' user=%s' % urllib.quote(ast.context.client) or u'',
                                                       ast and ast.request_guid or u'', desc % data)))
        data = ('%s\n%s\n' % (status, desc)) % data
        headers['Content-Type'] = 'text/plain'
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

def getParamEnv(suffix, default=None):
    return global_env.get(suffix, default)

"""
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
"""

class Application (webauthn2_handler_factory.RestHandler):
    "common parent class of all service handler classes to use db etc."

    def select_view_all(self):
        return self.select_files_by_predlist(subjpreds=[ web.Storage(tag='view', op=None, vals=[]) ],
                                             listtags=[ 'view', "view tags" ])

    def select_view(self, viewname=None, default='default'):
        return self.select_view_prioritized( [viewname, default] )
        
    def select_view_prioritized(self, viewnames=['default']):
        for viewname in viewnames:
            if viewname:
                view = view_cache.select(self.db, lambda : self.select_view_all(), self.context.client, viewname)
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
            (':!ciregexp:', 'Negated regular expression (case insensitive)'),
            (':word:', 'Word present in text search'),
            (':!word:', 'Word not present in text search'),
            (':tsquery:', 'Text search query') ]

    opsExcludeTypes = dict([ ('', ['tsvector']),
                             (':absent:', ['tsvector']),
                             ('=', ['','tsvector']),
                             ('!=', ['','tsvector']),
                             (':lt:', ['', 'boolean','tsvector']),
                             (':leq:', ['', 'boolean','tsvector']),
                             (':gt:', ['', 'boolean','tsvector']),
                             (':geq:', ['', 'boolean','tsvector']),
                             (':like:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean','tsvector']),
                             (':simto:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean','tsvector']),
                             (':regexp:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean','tsvector']),
                             (':!regexp:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean','tsvector']),
                             (':ciregexp:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean','tsvector']),
                             (':!ciregexp:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean','tsvector']),
                             (':word:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean']),
                             (':!word:', ['', 'int8', 'float8', 'date', 'timestamptz', 'boolean']) ])

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
                   (':!ciregexp:', '!~*'),
                   (':word:', '@@'),
                   (':!word:', '@@'),
                   (':tsquery:', '@@') ])
    
    static_tagdefs = []
    # -- the system tagdefs needed by the select_files_by_predlist call we make below and by Subject.populate_subject
    for prototype in [ ('config', 'text', None, False, 'subject', True),
                       ('config binding', 'int8', 'id', True, 'subject', False),
                       ('config parameter', 'text', None, False, 'subject', False),
                       ('config value', 'text', None, True, 'subject', False),
                       ('id', 'int8', None, False, 'system', True),
                       ('readok', 'boolean', None, False, 'system', False),
                       ('writeok', 'boolean', None, False, 'system', False),
                       ('tagdef', 'text', None, False, 'system', True),
                       ('tagdef dbtype', 'text', None, False, 'system', False),
                       ('tagdef tagref', 'text', 'tagdef', False, 'system', False),
                       ('tagdef tagref soft', 'boolean', None, False, 'system', False),
                       ('tagdef multivalue', 'boolean', None, False, 'system', False),
                       ('tagdef active', 'boolean', None, False, 'system', False),
                       ('tagdef readpolicy', 'text', None, False, 'system', False),
                       ('tagdef writepolicy', 'text', None, False, 'system', False),
                       ('tagdef unique', 'boolean', None, False, 'system', False),
                       ('tags present', 'text', 'tagdef', True, 'system', False),
                       ('tag read users', 'text', None, True, 'subjectowner', False),
                       ('tag write users', 'text', None, True, 'subjectowner', False),
                       ('read users', 'text', None, True, 'subjectowner', False),
                       ('write users', 'text', None, True, 'subjectowner', False),
                       ('owner', 'text', None, False, 'tagorowner', False),
                       ('modified', 'timestamptz', None, False, 'system', False),
                       ('subject last tagged', 'timestamptz', None, False, 'system', False),
                       ('subject last tagged txid', 'int8', None, False, 'system', False),
                       ('subject text', 'tsvector', None, False, 'system', False),
                       ('tag last modified', 'timestamptz', None, False, 'system', False),
                       ('name', 'text', None, False, 'subjectowner', True),
                       ('view', 'text', None, False, 'subject', True),
                       ('view tags', 'text', 'tagdef', True, 'subject', False) ]:
        deftagname, dbtype, tagref, multivalue, writepolicy, unique = prototype
        static_tagdefs.append(web.Storage(tagname=deftagname,
                                          owner=None,
                                          dbtype=dbtype,
                                          multivalue=multivalue,
                                          active=True,
                                          readpolicy='anonymous',
                                          readok=True,
                                          writepolicy=writepolicy,
                                          unique=unique,
                                          tagreaders=[],
                                          tagwriters=[],
                                          tagref=tagref,
                                          softtagref=False))

    static_tagdefs = dict( [ (tagdef.tagname, tagdef) for tagdef in static_tagdefs ] )

    rfc1123 = '%a, %d %b %Y %H:%M:%S UTC%z'

    def set_http_etag(self, txid):
        """Set an ETag from txid as main version key.

        """
        etag = []
        if 'Cookie' in self.http_vary:
            etag.append( '%s' % self.context.client )
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
        global db_cache

        webauthn2_handler_factory.RestHandler.__init__(self)
        self.context = Context()

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

        self.subjpreds = []

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

        myAppName = os.path.basename(web.ctx.env['SCRIPT_NAME'])

        self.hostname = web.ctx.host

        # TODO: get per-catalog config overrides from somewhere for multitenancy?
        self.config = web.Storage(global_env.items())
        self.config['home'] = self.config.get('home', 'https://%s' % self.hostname)
        self.config['homepath'] = self.config.get('home', self.config.home + web.ctx.homepath)
        self.config['store path'] = self.config.get('store path', '/var/www/%s-data' % self.config.get('user', 'tagfiler'))

        self.table_changes = {}
        
        self.logmsgs = []
        self.middispatchtime = None

        # BEGIN: get runtime parameters from database

        #self.log('TRACE', 'Application() constructor after static defaults')

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

    def accum_table_changes(self, table, count):
        x = self.table_changes.get(table, 0)
        self.table_changes[table] = x + count
        
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
        

    def validateTagdefDbtype(self, dbtype, tagdef=None, subject=None):
        """restrict value range for "tagdef dbtype"

           this is enforced during set_tag() during insert_tagdef() and cannot happen during bulk inserts
        """
        if dbtype not in set(['', 'boolean', 'int8', 'float8', 'text', 'date', 'timestamptz']):
            raise Conflict(self, 'Supplied dbtype "%s" is not supported.' % dbtype)

    def validateTagname(self, tag, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        if tag == '':
            raise Conflict(self, 'You must specify a defined tag name to set values for "%s".' % tagname)
        results = self.select_tagdef(tag)
        if len(results) == 0:
            raise Conflict(self, 'Supplied tag name "%s" is not defined.' % tag)

    def remapTagdefReadPolicy(self, pol):
        """remap read policies to their simplest functional equivalent based on graph ACL enforcement always present for reads"""
        map = dict(subject="anonymous",              # subject read enforcement already happens 
                   object="anonymous",               # object read enforcement already happens
                   tagandsubject="tag",              # subject read enforcement already happens
                   tagandsubjectandobject="tag",     # subject and object read enforcement already happens
                   subjectandobject="anonymous")     # subject and object read enforcement already happens
        if pol in map:
            return map[pol]
        else:
            return pol

    def validateTagdefPolicy(self, value, tagdef=None, subject=None):
        policies = set([ 
                'system',
                'subjectowner',
                'subject',
                'objectowner',
                'object',
                'subjectandobject',
                'tagandsubjectandobject',
                'tagorsubjectandobject',
                'tagandsubject',
                'tagorsubject',
                'tagorowner',
                'tagandowner',
                'tag',
                'anonymous'
                ])

        if value not in policies:
            raise Conflict(self, 'Supplied tagdef policy "%s" is not recognized.' % tag)

    def validateRole(self, role, tagdef=None, subject=None):
        # TODO: fixme with webauthn2
        pass
                
    def validateRolePattern(self, role, tagdef=None, subject=None):
        if role in [ '*' ]:
            return
        return self.validateRole(role)

    def getPolicyRule(self):
        srcroles = set(self.config['policy remappings'].keys()).intersection(self.context.attributes)

        if len(srcroles) == 1 or self.context.client == None:
            if self.context.client == None:
                # anonymous user, who we represent with empty string key in policy mappings
                # and use a safe default mapping if there is none 
                dstrole, readusers, writeusers, readok, writeok = self.config['policy remappings'].get('', 
                                                                                                       (self.config.admin, [], [], False, False))
            else:
                # authenticated user who we can map unambiguously
                srcrole = srcroles.pop()
                dstrole, readusers, writeusers, readok, writeok = self.config['policy remappings'][srcrole]

            readusers = [ u for u in readusers ]
            writeusers = [ u for u in writeusers ]
            if readok:
                readusers.append( self.context.client )
            if writeok:
                writeusers.append( self.context.client )
            return True, dstrole, readusers, writeusers
        elif len(srcroles) > 1:
            raise Conflict(self, "Ambiguous remap rules encountered for client roles %s. Please contact service administrator." % list(srcroles))
        else:
            return ( False, None, None, None )

    def doPolicyRule(self, newfile):
        remap, dstrole, readusers, writeusers = self.getPolicyRule()
        if not remap:
            return
        try:
            t = self.db.transaction()
            if readusers != None:
                self.delete_tag(newfile, self.tagdefsdict['read users'])
                for readuser in readusers:
                    self.set_tag(newfile, self.tagdefsdict['read users'], readuser)
                self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='read users', value=','.join(readusers))
            if writeusers != None:
                self.delete_tag(newfile, self.tagdefsdict['write users'])
                for writeuser in writeusers:
                    self.set_tag(newfile, self.tagdefsdict['write users'], writeuser)
                self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='write users', value=','.join(writeusers))
            if dstrole:
                self.set_tag(newfile, self.tagdefsdict['owner'], dstrole)
                self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='owner', value=dstrole)
            t.commit()
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception "%s" during owner remap attempt' % str(ev),
                      traceback.format_exception(et, ev, tb))
            t.rollback()
            raise

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

    def logfmt(self, action, dataset=None, tag=None, mode=None, user=None, value=None, txid=None, parts=None):
        if self.start_time:
            now = datetime.datetime.now(pytz.timezone('UTC'))
            elapsed = u'%d.%3.3d' % ( (now - self.start_time).seconds, (now - self.start_time).microseconds / 1000 )
            self.last_log_time = now
        else:
            elapsed = '-.---'
        if parts:
            msg = action + ' ' + ('%s' % parts)
        else:
            msg = self.logfmt_old(action, dataset, tag, mode, user, value, txid)
        return u'%ss %s%s req=%s -- %s' % (elapsed, web.ctx.ip, self.context.client and u' user=%s' % urlquote(self.context.client) or u'', 
                                           self.request_guid, msg)

    def log(self, action, dataset=None, tag=None, mode=None, user=None, value=None, txid=None):
        self.lograw(self.logfmt(action, dataset, tag, mode, user, value, txid))

    def txlog(self, action, dataset=None, tag=None, mode=None, user=None, value=None, txid=None):
        self.logmsgs.append(self.logfmt(action, dataset, tag, mode, user, value, txid))

    def txlog2(self, action, parts):
        self.logmsgs.append(self.logfmt(action, parts=parts))

    def preDispatchFake(self, uri, app):
        self.db = app.db
        self.context = app.context

    def preDispatchCore(self, uri, setcookie=True):
        self.request_uri = uri

        try:
            self.context = self.manager.get_request_context()
        except (ValueError, IndexError):
            # client is unauthenticated but require_client and/or require_attributes is enabled
            raise Unauthorized(self, 'tagfiler API usage by unauthorized client')
        
        self.middispatchtime = datetime.datetime.now()

    def preDispatch(self, uri):
        self.preDispatchCore(uri)

    def postDispatch(self, uri=None):
        pass

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

    def dbtransact(self, body, postCommit, limit=8):
        """re-usable transaction pattern

           using caller-provided thunks under boilerplate
           commit/rollback/retry logic
        """
        #self.log('TRACE', value='dbtransact() entered')

        def db_body(db):
            self.db = db

            self.logmsgs = []
            self.table_changes = {}
            self.subject = None
            self.datapred = None
            self.dataname = None
            self.dataid = None

            # build up globals useful to almost all classes, to avoid redundant coding
            # this is fragile to make things fast and simple

            self.tagdefsdict = dict([ (tagdef.tagname, tagdef) for tagdef in tagdef_cache.select(db, lambda: self.select_tagdef(), self.context.client) ])

            return body()

        # run under transaction control implemented by our parent class
        bodyval = self._db_wrapper(db_body)

        for msg in self.logmsgs:
            logger.info(myutf8(msg))
        self.logmsgs = []

        try:
            for table, count in self.table_changes.items():
                if count > cluster_threshold:
                    if bool(getParamEnv('transact cluster', False)):
                        self.dbquery('CLUSTER %s' % table)
                    if bool(getParamEnv('transact analyze', False)):
                        self.dbquery('ANALYZE %s' % table)
        except:
            pass

        return postCommit(bodyval)

    def acceptPair(self, s):
        parts = s.split(';')
        q = 1.0
        t = parts[0].strip()
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

    def preferredType(self):
        acceptTypes = self.acceptTypesPreferedOrder()
        if acceptTypes:
            for acceptType in acceptTypes:
                if acceptType in [ 'text/uri-list', 'application/x-www-form-urlencoded', 'text/csv', 'application/json', 'text/plain' ]:
                    return acceptType
        return None
                           
    # a bunch of little database access helpers for this app, to be run inside
    # the dbtransact driver

    def validate_subjpreds_unique(self, acceptBlank=False, restrictSchema=False, subjpreds=None):
        """Evaluate subjpreds (default self.subjpreds) for subject-identifying uniqueness.

           Raises Conflict if restrictSchema=True and additional
           criteria are not met:

              1. no preds are ambiguous, e.g. can be used with set_tag
              2. no preds involve writeok=False tagdefs

           Returns (in prioritized order):

              True if subjpreds is uniquely constraining

              None if subjpreds is not constraining AND acceptBlank==True

           Else raises Conflict

        """
        if subjpreds == None:
            subjpreds = self.subjpreds
        unique = None
        for pred in subjpreds:
            tagdef = self.tagdefsdict.get(pred.tag, None)
            if tagdef == None:
                raise Conflict(self, 'Tag "%s" referenced in subject predicate list is not defined on this server.' % pred.tag)

            if restrictSchema:
                if tagdef.writeok == False:
                    raise Conflict(self, 'Subject predicate sets restricted tag "%s".' % tagdef.tagname)
                if tagdef.dbtype == '' and pred.op or \
                       tagdef.dbtype != '' and pred.op != '=':
                    raise Conflict(self, 'Subject predicate has inappropriate operator "%s" on tag "%s".' % (pred.op, tagdef.tagname))
                    
            if tagdef.get('unique', False) and pred.op == '=' and pred.vals:
                unique = True
                
        if unique:
            return True
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
            if len(set(self.context.attributes)
                   .union(set(['*']))
                   .intersection(set(subject['write users'] or []))) > 0:
                return True
            elif self.context.client:
                return False
            else:
                return None
        else:
            return True

    def test_tag_authz(self, mode, subject, tagdef, value=None, tagdefs=None):
        """Check whether access is allowed to user given policy_tag and owner.

           True: access allowed
           False: access forbidden
           None: user needs to authenticate to be sure
                 or subject is None and subject is needed to make determination
                 or value is None and value is needed to make determination"""
        if tagdefs is None:
            tagdefs = self.tagdefsdict

        policy = tagdef['%spolicy' % mode]

        tag_ok = tagdef.owner in self.context.attributes \
                 or len(set([ r for r in self.context.attributes])
                        .union(set(['*']))
                        .intersection(set(tagdef['tag' + mode[0:4] + 'ers'] or []))) > 0

        if subject:
            subject_ok = dict(read=True, write=subject.writeok)[mode]
            subject_owner = subject.owner in self.context.attributes
        else:
            subject_ok = None
            subject_owner = None

        obj_ok = None
        obj_owner = None

        if tagdef.tagref and (not tagdef.softtagref):
            reftagdef = tagdefs[tagdef.tagref]

            if value is not None and obj_ok is None:
                results = self.select_files_by_predlist_path([web.Storage(tag=tagdef.tagref, op='=', vals=[value])], tagdefs=tagdefs)
                if len(results) == 1:
                    obj = results[0]
                    obj_ok = self.test_tag_authz(mode, obj, reftagdef, tagdefs=tagdefs)
                    obj_owner = ('*' in self.context.attributes) or (obj.owner in self.context.attributes)
                else:
                    # this could happen on simple tag writes
                    raise Conflict(self, data='Referenced object "%s"="%s" is not found.' % (tagdef.tagref, value))

        if policy == 'system':
            return False
        elif policy == 'subjectowner':
            return subject_owner
        elif policy == 'subject':
            return subject_ok
        elif policy == 'objectowner':
            return obj_owner
        elif policy == 'object':
            return obj_ok
        elif policy == 'subjectandobject':
            return subject_ok and obj_ok
        elif policy == 'tagandsubjectandobject':
            return tag_ok and subject_ok and obj_ok
        elif policy == 'tagorsubjectandobject':
            return tag_ok or (subject_ok and obj_ok)
        elif policy == 'tagandsubject':
            return tag_ok and subject_ok
        elif policy == 'tagorsubject':
            return tag_ok or subject_ok
        elif policy == 'tagorowner':
            return tag_ok or subject_owner
        elif policy == 'tagandowner':
            return tag_ok and subject_owner
        elif policy == 'tag':
            return tag_ok
        else:
            # policy == 'anonymous'
            return True

    def test_tagdef_authz(self, mode, tagdef):
        """Check whether access is allowed."""
        if mode == 'read':
            return True
        elif self.context.client:
            return tagdef.owner in self.context.attributes
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

    def enforce_tag_authz(self, mode, subject, tagdef, value=None):
        """Check whether access is allowed and throw web exception if not."""
        allow = self.test_tag_authz(mode, subject, tagdef, value)
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
        for dtype in [ 'tagdef', 'config', 'view', 'file' ] \
                + [ tagdef.tagname for tagdef in self.tagdefsdict.values() if tagdef.unique and tagdef.tagname if tagdef.tagname != 'id' ] \
                + [ 'id' ] :
            keyv = subject.get(dtype, None)
            if keyv:
                return dtype

    def subject2identifiers(self, subject):
        try:
            # try to follow dtype from DB
            dtype = subject.dtype
        except:
            dtype = self.classify_subject(subject)

        datapred = None
        dataid = None
        dataname = None
        if dtype not in [ 'file' ]:
            keyv = subject.get(dtype, None)
        else:
            keyv = None

        if keyv:
            if self.tagdefsdict[dtype].multivalue:
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

    def insert_file(self, file=None):
        newid = self.dbquery("INSERT INTO resources DEFAULT VALUES RETURNING subject")[0].subject
        subject = web.Storage(id=newid)
        
        self.set_tag_lastmodified(subject, self.tagdefsdict['id'])

        if file:
            self.set_tag(subject, self.tagdefsdict['file'], file)

        return newid

    def delete_file(self, subject, allow_tagdef=False):
        wheres = []

        if subject.get('tagdef', None) != None and not allow_tagdef:
            raise Conflict(self, u'Delete of subject tagdef="' + subject.tagdef  + u'" not supported; use dedicated /tagdef/ API.')

        results = self.dbquery('SELECT * FROM "_tags present" WHERE subject = $subject', vars=dict(subject=subject.id))
        for result in results:
            self.set_tag_lastmodified(None, self.tagdefsdict[result.value])
        self.set_tag_lastmodified(None, self.tagdefsdict['id'])
        
        query = 'DELETE FROM resources WHERE subject = $id'
        self.dbquery(query, vars=dict(id=subject.id))

    tagdef_listas =  { 'tagdef': 'tagname', 
                       'tagdef dbtype': 'dbtype',
                       'tagdef tagref': 'tagref',
                       'tagdef tagref soft': 'softtagref',
                       'tagdef multivalue': 'multivalue',
                       'tagdef active': 'active',
                       'tagdef readpolicy': 'readpolicy',
                       'tagdef writepolicy': 'writepolicy',
                       'tagdef unique': 'unique',
                       'tag read users': 'tagreaders',
                       'tag write users': 'tagwriters',
                       'tag last modified': 'modified' }

    def select_tagdef(self, tagname=None, subjpreds=[], order=None, enforce_read_authz=True):
        listtags = [ 'owner', 'id' ]
        listtags = listtags + Application.tagdef_listas.keys()

        if order:
            if type(order) == tuple:
                ordertags = [ order ]
            else:
                ordertags = [ ( order, ':asc:') ]
        else:
            ordertags = []

        subjpreds = subjpreds + [ web.Storage(tag='tagdef', op=None, vals=[]) ]

        results = list(self.select_files_by_predlist(subjpreds, listtags, ordertags, listas=Application.tagdef_listas, tagdefs=Application.static_tagdefs, enforce_read_authz=enforce_read_authz))

        tagdefs = dict([ (tagdef.tagname, tagdef) for tagdef in results ])

        for tagdef in results:
            for mode in ['read', 'write']:
                tagdef['%sok' % mode] = self.test_tag_authz(mode, None, tagdef, tagdefs=tagdefs)

            tagdef['reftags'] = set()

        for tagdef in results:
            if tagdef.tagref and not tagdef.softtagref:
                tagdefs[tagdef.tagref].reftags.add(tagdef.tagname)

        #web.debug(results)
        if tagname:
            if tagname in tagdefs:
                return [ tagdefs[tagname] ]
            else:
                return []
        else:
            return results

    def exists_tagdef(self, tagname, enforce_read_authz=True):
        listtags = [ 'tagdef' ]

        subjpreds = [ web.Storage(tag='tagdef', op='=', vals=[tagname]) ]

        results = self.select_files_by_predlist(subjpreds, listtags, tagdefs=Application.static_tagdefs, enforce_read_authz=enforce_read_authz)

        if len(results) == 0:
            return False
        else:
            return True

    def insert_tagdef(self):
        #self.log('TRACE', 'Application.insert_tagdef() entered')
        if self.exists_tagdef(self.tag_id, enforce_read_authz=False):
            raise Conflict(self, 'Tagdef "%s" already exists. Delete it before redefining.' % self.tag_id)

        if self.dbtype is None:
            # force default empty type
            self.dbtype = ''

        owner = self.context.client
        newid = self.insert_file(None)
        subject = web.Storage(id=newid)
        tags = [ ('created', 'now'),
                 ('tagdef', self.tag_id),
                 ('tagdef active', None),
                 ('tagdef dbtype', self.dbtype),
                 ('tagdef readpolicy', self.remapTagdefReadPolicy(self.readpolicy)),
                 ('tagdef writepolicy', self.writepolicy),
                 ('read users', '*') ]
        if owner:
            tags.append( ('owner', owner) )
        if self.tagref:
            tags.append( ('tagdef tagref', self.tagref) )
            if self.softtagref:
                tags.append( ('tagdef tagref soft', True) )
        if not self.tagref or self.softtagref:
            if self.readpolicy.find('object') >= 0 or self.writepolicy.find('object') >= 0:
                raise Conflict(self, 'Owner-based access policies only allowed in combination with hard tagrefs.')
        if self.multivalue:
            try:
                self.multivalue = downcast_value('boolean', self.multivalue)
            except ValueError, e:
                raise Conflict(self, data=str(e))
            tags.append( ('tagdef multivalue', self.multivalue) )
        else:
            tags.append( ('tagdef multivalue', False) )
        if self.is_unique:
            try:
                self.is_unique = downcast_value('boolean', self.is_unique)
            except ValueError, e:
                raise Conflict(self, data=str(e))
            tags.append( ('tagdef unique', self.is_unique) )
        else:
            tags.append( ('tagdef unique', False) )

        tagdef = web.Storage([ (Application.tagdef_listas.get(key, key), value) for key, value in tags ])
        tagdef.id = newid
        if owner is None:
            tagdef.owner = None
        if self.tagref is None:
            tagdef.tagref = None
        if self.tagref and self.softtagref:
            tagdef.softtagref = True
        else:
            tagdef.softtagref = False
        tagdef.multivalue = self.multivalue
        
        self.deploy_tagdef(tagdef)
        #self.log('TRACE', 'Application.insert_tagdef() after deploy')

        for tag, value in tags:
            self.set_tag(subject, self.tagdefsdict[tag], value)

        self.dbquery('ANALYZE "_tagdef"')
        self.dbquery('ANALYZE "_tagdef tagref"')

        return tagdef
        
    def get_index_name(self, tablename, indexcols):
        sql = ('SELECT indexname FROM pg_catalog.pg_indexes' 
               + " WHERE tablename = %s" % wrapval(tablename)
               + " AND indexdef ~ %s" % wrapval('[(]%s( text_pattern_ops)?[)]' % ', '.join(indexcols)) )
        results = self.dbquery(sql)
        if len(results) != 1:
            web.debug(sql)
            web.debug(list(results))
            web.debug(list(self.dbquery('SELECT indexname, indexdef FROM pg_catalog.pg_indexes WHERE tablename = %s' % wrapval(tablename))))
            raise IndexError()
        else:
            return results[0].indexname

    def deploy_tagdef(self, tagdef):
        tabledef = "CREATE TABLE %s" % (self.wraptag(tagdef.tagname))
        tabledef += " ( subject bigint NOT NULL REFERENCES resources (subject) ON DELETE CASCADE"
        indexdef = ''
        clustercmd = ''

        dbtype = tagdef.dbtype
        tagref = tagdef.tagref
        if dbtype is None:
            dbtype = ''

        if dbtype != '':
            tabledef += ", value %s" % dbtype
            if dbtype == 'text':
                tabledef += " DEFAULT ''"
            elif dbtype == 'boolean':
                tabledef += ' DEFAULT False'
            tabledef += ' NOT NULL'

            if tagdef.unique:
                tabledef += ' UNIQUE'

            if tagref:
                referenced_tagdef = self.tagdefsdict.get(tagref, None)

                if referenced_tagdef == None:
                    raise Conflict(self, 'Referenced tag "%s" not found.' % tagref)

                if not referenced_tagdef.unique:
                    raise Conflict(self, 'Referenced tag "%s" is not unique.' % tagref)

                if referenced_tagdef.dbtype != tagdef.dbtype:
                    raise Conflict(self, 'Referenced tag "%s" must have identical dbtype.' % tagref)

                if not tagdef.softtagref:
                    if referenced_tagdef.tagname == 'id':
                        tabledef += ' REFERENCES resources (subject) ON DELETE CASCADE'
                    else:
                        tabledef += ' REFERENCES %s (value) ON DELETE CASCADE' % self.wraptag(tagref)
                
            if dbtype == 'text':
                tabledef += ', tsv tsvector'

            if not tagdef.multivalue:
                tabledef += ", UNIQUE(subject)"
            else:
                tabledef += ", UNIQUE(subject, value)"

            indexdef = 'CREATE INDEX %s' % (self.wraptag(tagdef.tagname, '_value_idx'))
            indexdef += ' ON %s' % (self.wraptag(tagdef.tagname))
            indexdef += ' (value %s)' % (dbtype == 'text' and 'text_pattern_ops' or '')
        else:
            tabledef += ', UNIQUE(subject)'

        tabledef += " )"
        #web.debug(tabledef)
        self.dbquery(tabledef)
        if indexdef:
            self.dbquery(indexdef)
        if dbtype == 'text':
            self.dbquery('CREATE TRIGGER tsvupdate BEFORE INSERT OR UPDATE ON %s' % self.wraptag(tagdef.tagname)
                         + " FOR EACH ROW EXECUTE PROCEDURE tsvector_update_trigger(tsv, 'pg_catalog.english', value)")
            self.dbquery('CREATE INDEX %s ON %s USING gin(tsv)' % (
                    self.wraptag(tagdef.tagname, '_tsv_idx'),
                    self.wraptag(tagdef.tagname)
                    ))

        if not tagdef.multivalue:
            clusterindex = self.get_index_name('_' + tagdef.tagname, ['subject'])
        else:
            clusterindex = self.get_index_name('_' + tagdef.tagname, ['subject', 'value'])
        clustercmd = 'CLUSTER %s USING %s' % (self.wraptag(tagdef.tagname), self.wraptag(clusterindex, prefix=''))
        self.dbquery(clustercmd)

    def delete_tagdef(self, tagdef):
        #self.log('TRACE', 'Application.delete_tagdef() entered')
        path = [ ([ web.Storage(tag='tagdef tagref', op='=', vals=[tagdef.tagname]) ],
                  [ web.Storage(tag='tagdef', op=None, vals=[]) ],
                  []) ]

        # TODO: change this from a Conflict to a cascading delete of all referencing tagdefs?
        results = self.select_files_by_predlist_path(path, enforce_read_authz=False)
        if len(results) > 0:
            raise Conflict(self, 'Tagdef "%s" cannot be removed while it is referenced by one or more other tagdefs: %s.' % (
                    tagdef.tagname,
                    ', '.join([ '"%s"' % td.tagdef for td in results ])
                    ))

        self.undeploy_tagdef(tagdef)

        tagdef.name = None
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
            
        if tagdef.dbtype != '' and value != None:
            if value == '':
                wheres.append('tag.value IS NULL')
            else:
                vars['value'] = value
                wheres.append('tag.value = $value')

        query = 'SELECT tag.* FROM %s AS tag' % self.wraptag(tagdef.tagname)

        if wheres:
            query += ' WHERE ' + ' AND '.join(wheres)

        if tagdef.dbtype != '':
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
            wheres.append("value = $tagname")
        
        wheres = ' AND '.join(wheres)
        if wheres:
            wheres = " WHERE " + wheres
            
        query = 'SELECT subject AS id, value AS tagname FROM "_tags present"' \
                + wheres \
                + " ORDER BY subject, value"
        
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

        # update virtual tags based on their source tags
        if tagdef.tagname in ['read users', 'owner']:
            self.set_tag_lastmodified(None, self.tagdefsdict['readok'])
            
        if tagdef.tagname in ['write users', 'owner']:
            self.set_tag_lastmodified(None, self.tagdefsdict['writeok'])
            

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
        deleted = self.dbquery(query, vars=dict(id=subject.id, value=value, tagname=tagdef.tagname))
        if len(deleted) > 0:
            self.set_tag_lastmodified(subject, tagdef)

            results = self.select_tag_noauthn(subject, tagdef)
            if len(results) == 0 and tagdef.tagname != 'tags present':
                self.delete_tag(subject, self.tagdefsdict['tags present'], tagdef.tagname)

            # update in-memory representation too for caller's sake
            if tagdef.multivalue:
                subject[tagdef.tagname] = [ res.value for res in self.select_tag_noauthn(subject, tagdef) ]
            elif tagdef.dbtype != '':
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
        if tagdef.writepolicy != 'system':
            # only run extra validation on user-provided values...
            validator = Application.tagnameValidators.get(tagdef.tagname)
            if validator:
                validator(self, value, tagdef, subject)

            def convert(v):
                try:
                    return downcast_value(tagdef.dbtype, v)
                except ValueError, e:
                    raise Conflict(self, data=str(e))

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
                if tagdef.dbtype != '':
                    raise Conflict(self, 'Tag "%s" is defined as unique and value "%s" is already bound to another subject.' % (tagdef.tagname, value))
                else:
                    raise Conflict(self, 'Tag "%s" is defined as unique is already bound to another subject.' % (tagdef.tagname))

        if tagdef.tagref and (not tagdef.softtagref) and value is not None:
            reftagdef = self.tagdefsdict[tagdef.tagref]
            results = self.select_tag_noauthn(None, reftagdef, value)
            if len(results) == 0:
                raise Conflict(self, 'Provided value or values for tag "%s" are not valid references to existing tags "%s"' % (tagdef.tagname, tagdef.tagref))

        # check whether triple already exists
        results = self.select_tag_noauthn(subject, tagdef, value)
        if len(results) > 0:
            return

        vars = dict(subject=subject.id, value=value, tagname=tagdef.tagname)

        if not tagdef.multivalue:
            # check pre-conditions before inserting triple
            if tagdef.dbtype == '':
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
        if tagdef.dbtype != '' and value != None:
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
        elif tagdef.dbtype != '':
            subject[tagdef.tagname] = self.select_tag_noauthn(subject, tagdef)[0].value
        else:
            subject[tagdef.tagname] = True
        
        if tagdef.tagname != 'tags present':
            results = self.select_filetags_noauthn(subject, tagdef.tagname)
            if len(results) == 0:
                self.set_tag(subject, self.tagdefsdict['tags present'], tagdef.tagname)

        self.set_tag_lastmodified(subject, tagdef)
        

    def set_tag_intable(self, tagdef, intable, idcol, valcol, flagcol, wokcol, isowncol, enforce_tag_authz=True, set_mode='merge', unnest=True, wheres=[], test=True, depth=0, newcol=None, nowval='now'):
        """Perform bulk-setting of tags from an input table.

           tagdef:  the tag to update
           intable: the table name or table expression for the input data with following columns...
               -- requires idcol to already be populated by the caller
           
           idcol:   the col name for the subject id of input subject, value triples
           valcol:  the col name or value expression for the value of input subject, value triples
           flagcol: the col name for tracking updated subjects
           wokcol:  the col name for checking subject writeok status
           isowncol: the col name for checking subject is_owner status

           enforce_tag_authz: whether to follow tagdef's write authz policy
               -- requires wokcol and isowncol to already be populated by caller

           set_mode   = 'merge' combines new triples with existing as appropriate
                      = 'replace' sets tag-value set to input set (removing all others from graph)

           unnest     = True:  idcol, unnest(valcol) produces set of triples for multivalue tags
                      = False: idcol, valcol produces set of triples for multivalue tags

           wheres     = list of where clauses limiting which input rows get processed
               -- will be combined in conjunction (AND)

           test       = True: perform uniqueness tests; False: skip tests

           depth      = internally-managed recursion tracking for unique temporary table names
        """
        #self.log('TRACE', 'Application.set_tag_intable("%s",d=%d) entered' % (tagdef.tagname, depth))

        if len(wheres) == 0:
            # we require a non-empty list for SQL constructs below...
            wheres = [ 'True' ]
        
        if tagdef.tagref and (not tagdef.softtagref):
            # tagdef write policy may depend on per-object information
            reftagdef = self.tagdefsdict[tagdef.tagref]
            refval = valcol
            refcol = wraptag(tagdef.tagref, prefix='')
            if reftagdef.multivalue:
                refcol = 'unnest(%s)' % refcol
            if tagdef.multivalue and unnest:
                refval = 'unnest(%s)' % refval
            refquery, refvalues = self.build_files_by_predlist_path([ ([web.Storage(tag=tagdef.tagref, op=None, vals=[])],
                                                                       [web.Storage(tag=tagdef.tagref, op=None, vals=[]),
                                                                        web.Storage(tag='owner', op=None, vals=[]),
                                                                        web.Storage(tag='writeok', op=None, vals=[])],
                                                                       []) ],
                                                                    enforce_read_authz=enforce_tag_authz)
        else:
            refquery = None
            refcol = None
            refval = None

        rolekeys = ','.join([ wrapval(r, 'text') for r in set(self.context.attributes).union(set(['*'])) ])
        
        if enforce_tag_authz:
            # do the write-authz tests for the active set of intable rows
            if tagdef.writeok == False:
                # tagdef write policy fails statically for this user and tag
                raise Forbidden(self, data='write on tag "%s"' % tagdef.tagname)
            elif tagdef.writeok == None:
                # tagdef write policy depends on per-row information
                if tagdef.writepolicy in [ 'subject', 'tagorsubject', 'tagandsubject', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                    # None means we need subject writeok for this user
                    results = self.dbquery('SELECT True AS unauthorized FROM %(intable)s WHERE %(wheres)s LIMIT 1'
                                           % dict(intable=intable,
                                                  wheres=' AND '.join([ 'coalesce(NOT %s, True)' % wokcol ] + wheres)))
                    if len(results) > 0:
                        raise Forbidden(self, data='write on tag "%s" for one or more matching subjects' % tagdef.tagname)
                    
                if tagdef.writepolicy in [ 'subjectowner', 'tagorowner', 'tagandowner' ]:
                    # None means we need subject is_owner for this user
                    query = 'SELECT True AS unauthorized FROM %(intable)s WHERE %(wheres)s LIMIT 1' % dict(intable=intable,
                                                                                                           wheres=' AND '.join([ '%s = False' % isowncol ] + wheres))
                    results = self.dbquery(query)
                    if len(results) > 0:
                        raise Forbidden(self, data='write on tag "%s" for one or more matching subjects' % tagdef.tagname)

                if tagdef.writepolicy in [ 'object', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                    # None means we need object writeok for this user
                    query = (('SELECT True AS unauthorized FROM (SELECT %(refval)s AS val FROM %(intable)s s WHERE %(wheres)s ) s'
                              + ' JOIN (%(refquery)s) r ON (s.val = r.%(refcol)s)'
                              + ' WHERE coalesce(NOT r.writeok, True)'
                              + ' LIMIT 1'
                              ) % dict(intable=intable, refquery=refquery, refcol=refcol, refval=refval, wheres=' AND '.join(wheres)))
                    results = self.dbquery(query, vars=refvalues)
                    if len(results) > 0:
                        raise Forbidden(self, data='write on tag "%s" for one or more matching objects' % tagdef.tagname)

                if tagdef.writepolicy in [ 'objectowner' ]:
                    # None means we need object is_owner for this user
                    query = (('SELECT True AS unauthorized FROM (SELECT %(refval)s AS val FROM %(intable)s s WHERE %(wheres)s ) s'
                              + ' JOIN (%(refquery)s) r ON (s.val = r.%(refcol)s)'
                              + ' WHERE coalesce(r.owner NOT IN (%(rolekeys)s), True)'
                              + ' LIMIT 1'
                              ) % dict(intable=intable, refquery=refquery, refcol=refcol, refval=refval, wheres=' AND '.join(wheres), rolekeys=rolekeys))
                    results = self.dbquery(query, vars=refvalues)
                    if len(results) > 0:
                        raise Forbidden(self, data='write on tag "%s" for one or more matching objects' % tagdef.tagname)
            else:
                # tagdef write policy accepts statically for this user and tag
                pass
            
            #self.log('TRACE', 'Application.set_tag_intable("%s",d=%d) authz enforced' % (tagdef.tagname, depth))

        table = wraptag(tagdef.tagname)
        count = 0

        if test and tagdef.tagref and (not tagdef.softtagref):
            # need to validate referential integrity of user input on visible graph content
            query = (('SELECT True AS notfound'
                      + ' FROM (SELECT %(refval)s AS val FROM %(intable)s s) s'
                      + ' LEFT OUTER JOIN (%(refquery)s) r ON (s.val = r.%(refcol)s)'
                      + ' WHERE r.%(refcol)s IS NULL'
                      + ' LIMIT 1'
                      ) % dict(intable=intable, refquery=refquery, refcol=refcol, refval=refval))
            results = self.dbquery(query, vars=refvalues)
            if len(results) > 0:
                raise Conflict(self, data='Provided value or values for tag "%s" are not valid references to existing tags "%s"' % (tagdef.tagname, tagdef.tagref))

            #self.log('TRACE', 'Application.set_tag_intable("%s",d=%d) tagref=%s integrity checked' % (tagdef.tagname, depth, tagdef.tagref))

        if test and tagdef.unique:
            # test for uniqueness violations... already enforced uniqueness in table and intable via table constraints
            results = self.dbquery(('SELECT True AS inconsistent'
                                    + ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value FROM %(intable)s WHERE %(wheres)s) AS i'
                                    + ' JOIN %(table)s AS t USING (value)'
                                    + ' WHERE i.subject != t.subject'
                                    + ' LIMIT 1'
                                    ) % dict(intable=intable, table=table, idcol=idcol, valcol=valcol, wheres=' AND '.join(wheres)))
            if len(results) > 0:
                raise Conflict(self, 'Duplicate value violates uniqueness constraint for tag "%s".' % tagdef.tagname)
                
            #self.log('TRACE', 'Application.set_tag_intable("%s",d=%d) uniqueness checked' % (tagdef.tagname, depth))

        parts = dict(table=table,
                     intable=intable,
                     idcol=idcol,
                     valcol=tagdef.multivalue and unnest and 'unnest(%s)' % valcol or valcol,
                     flagcol=flagcol,
                     isowncol=isowncol,
                     newcol=newcol,
                     tagname=wrapval(tagdef.tagname),
                     tagspresent=wraptag('tags present'),
                     rolekeys=rolekeys,
                     wheres=' AND '.join(wheres))

        if tagdef.multivalue:
            # multi-valued tags are straightforward set-algebra on triples
            
            if set_mode == 'replace':
                # clear graph triples not present in input
                raise NotImplementedError()

            # add input triples not present in graph

            # old subjects need presence test in existing graph data
            oldsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s AND NOT %(newcol)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject, value)'
                + '     WHERE t.subject IS NULL AND i2.value IS NOT NULL'
                )
            # new subjects have all new triples
            newsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s AND %(newcol)s) i2'
                + '     WHERE i2.value IS NOT NULL'
                )

            # mixed new and old subjects need presence test in existing graph data
            allsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject, value)'
                + '     WHERE t.subject IS NULL AND i2.value IS NOT NULL'
                )

            #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) multi-value update entered' % (tagdef.tagname, depth))

            if newcol:
                if flagcol and tagdef.tagname not in ['tags present']:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT DISTINCT subject' + oldsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT DISTINCT subject' + newsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) multi-value update inserts flagged' % (tagdef.tagname, depth))

                if tagdef.tagname not in ['tags present', 'id', 'readok', 'writeok']:
                    self.set_tag_intable(self.tagdefsdict['tags present'], 
                                         ('(SELECT DISTINCT subject, False AS created' + oldsubj_newtrips_query_frag
                                          + ' UNION ALL '
                                          ' SELECT DISTINCT subject, True AS created' + newsubj_newtrips_query_frag + ')'
                                          ) % parts,
                                         idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', test=False,
                                         flagcol=None, wokcol=None, isowncol=None, enforce_tag_authz=False, set_mode='merge', unnest=False, depth=depth+1, newcol='created')

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) multi-value update presence updated' % (tagdef.tagname, depth))

                query = ('INSERT INTO %(table)s (subject, value)'
                         + ' SELECT subject, value' + oldsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query)

                query = ('INSERT INTO %(table)s (subject, value)'
                         + ' SELECT subject, value' + newsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query) 

                #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) multi-value update inserts performed' % (tagdef.tagname, depth))
            else:
                if flagcol and tagdef.tagname not in ['tags present']:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT DISTINCT subject' + allsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) multi-value update inserts flagged (B)' % (tagdef.tagname, depth))

                if tagdef.tagname not in ['tags present', 'id', 'readok', 'writeok']:
                    self.set_tag_intable(self.tagdefsdict['tags present'], 
                                         ('(SELECT DISTINCT subject' + allsubj_newtrips_query_frag + ')'
                                          ) % parts,
                                         idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', test=False,
                                         flagcol=None, wokcol=None, isowncol=None, enforce_tag_authz=False, set_mode='merge', unnest=False, depth=depth+1)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) multi-value update presence updated (B)' % (tagdef.tagname, depth))

                query = ('INSERT INTO %(table)s (subject, value)'
                         + ' SELECT subject, value' + allsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query)

                #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) multi-value update inserts performed(B)' % (tagdef.tagname, depth))

        elif tagdef.dbtype != '':
            # single-valued tags require insert-or-update due to cardinality constraint
            
            if set_mode == 'replace':
                raise NotImplementedError()

            # update old triples with wrong value

            # old subjects need presence test in existing graph data
            oldsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s AND NOT %(newcol)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject)'
                + '     WHERE t.subject IS NULL AND i2.value IS NOT NULL'
                )
            # old subjects need presence test in existing graph data
            oldsubj_updtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s AND NOT %(newcol)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject)'
                + '     WHERE t.subject IS NOT NULL AND i2.value != t.value'
                )
            # new subjects have all new triples
            newsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s AND %(newcol)s) i2'
                + '     WHERE i2.value IS NOT NULL'
                )

            # mixed new and old subjects need presence test in existing graph data
            allsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject)'
                + '     WHERE t.subject IS NULL AND i2.value IS NOT NULL'
                )
            # mixed new and old subjects need presence test in existing graph data
            allsubj_updtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject)'
                + '     WHERE t.subject IS NOT NULL AND i2.value != t.value'
                )

            #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update entered' % (tagdef.tagname, depth))

            reftags = self.tagdef_reftags_closure(tagdef)
            mtable = wraptag(self.request_guid, '', 'tmp_refmod_%d_' % depth)   # modified subjects for metadata tracking

            if reftags and (not flagcol or not isowncol):
                self.dbquery("CREATE TEMPORARY TABLE %(mtable)s (id int8 PRIMARY KEY)" % dict(mtable=mtable))

            if newcol:
                # replacement of existing values causes implicit delete of referencing tags
                for reftag in reftags:
                    reftagdef = self.tagdefsdict[reftag]
                    reftable = self.wraptag(reftag)

                    # ON UPDATE CASCADE would not do what we want, so manually delete stale references
                    # also track the modified subjects
                    if flagcol and isowncol:
                        # propogate modified subjects to caller via intable.flagcol
                        query = ("WITH deletions AS ("
                                 + " DELETE FROM %s r" % reftable
                                 + " USING "
                                 + "   (SELECT subject, i2.value" + oldsubj_updtrips_query_frag + ') AS i,'
                                 + "   %(table)s AS t"
                                 + " WHERE r.value = t.value AND i.subject = t.subject AND i.value != t.value"
                                 + " RETURNING r.subject"
                                 + "),"
                                 + " updates AS ("
                                 + " UPDATE %(intable)s i SET %(flagcol)s = True"
                                 + " FROM (SELECT DISTINCT subject FROM deletions) d"
                                 + " WHERE i.%(idcol)s = d.subject AND NOT i.%(flagcol)s"
                                 + ")"
                                 + " INSERT INTO %(intable)s (%(idcol)s, %(flagcol)s, %(isowncol)s)"
                                 + " SELECT DISTINCT d.subject, True, coalesce(o.value IN (%(rolekeys)s), False)"
                                 + " FROM deletions d"
                                 + " LEFT OUTER JOIN %(intable)s i ON (d.subject = i.%(idcol)s)"
                                 + " LEFT OUTER JOIN _owner o ON (d.subject = o.subject)"
                                 + " WHERE i.%(idcol)s IS NULL"
                                  ) % parts
                    else:
                        # track modified subjects in mtable
                        query = ("WITH deletions AS ("
                                 + " DELETE FROM %s r" % reftable
                                 + " USING "
                                 + "   (SELECT subject, i2.value" + oldsubj_updtrips_query_frag + ') AS i,'
                                 + "   %(table)s AS t"
                                 + " WHERE r.value = t.value AND i.subject = t.subject AND i.value != t.value"
                                 + " RETURNING r.subject"
                                 + ")"
                                 + " INSERT INTO %s" % mtable
                                 + " SELECT DISTINCT d.subject FROM deletions d"
                                 + " LEFT OUTER JOIN %s m ON (d.subject = m.id)" % mtable
                                 + " WHERE m.id IS NULL"
                                 ) % parts
                    #web.debug(reftag, query)
                    self.dbquery(query)

                if reftags:
                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update reftags chased' % (tagdef.tagname, depth))
                    pass

                if flagcol:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT subject' + oldsubj_updtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update mutations flagged' % (tagdef.tagname, depth))

                # update triples where graph had a different value than non-null input
                query = ('UPDATE %(table)s AS t SET value = i.value'
                         + ' FROM (SELECT i2.subject, i2.value' + oldsubj_updtrips_query_frag + ') AS i'
                         + ' WHERE t.subject = i.subject AND t.value != i.value'
                    ) % parts
                #web.debug(query)
                count += self.dbquery(query) # only run update for old subjects

                #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update mutations applied' % (tagdef.tagname, depth))
            else:
                # replacement of existing values causes implicit delete of referencing tags
                for reftag in reftags:
                    reftagdef = self.tagdefsdict[reftag]
                    reftable = self.wraptag(reftag)
                    
                    # ON UPDATE CASCADE would not do what we want, so manually delete stale references
                    # also track the modified subjects
                    if flagcol and isowncol:
                        # propogate modified subjects to caller via intable.flagcol
                        query = ("WITH deletions AS ("
                                 + " DELETE FROM %s r" % reftable
                                 + " USING "
                                 + "   (SELECT subject, i2.value" + allsubj_updtrips_query_frag + ') AS i,'
                                 + "   %(table)s AS t"
                                 + " WHERE r.value = t.value AND i.subject = t.subject AND i.value != t.value"
                                 + " RETURNING r.subject"
                                 + "),"
                                 + " updates AS ("
                                 + " UPDATE %(intable)s AS i SET %(flagcol)s = True"
                                 + " FROM (SELECT DISTINCT subject FROM deletions) d"
                                 + " WHERE i.%(idcol)s = d.subject AND NOT i.%(flagcol)s"
                                 + ")"
                                 + " INSERT INTO %(intable)s (%(idcol)s, %(flagcol)s, %(isowncol)s)"
                                 + " SELECT DISTINCT d.subject, True, coalesce(o.value IN (%(rolekeys)s), False)"
                                 + " FROM deletions d"
                                 + " LEFT OUTER JOIN %(intable)s i ON (d.subject = i.%(idcol)s)"
                                 + " LEFT OUTER JOIN _owner o ON (d.subject = o.subject)"
                                 + " WHERE i.%(idcol)s IS NULL"
                                 ) % parts
                    else:
                        # track modified subjects in mtable
                        query = ("WITH deletions AS ("
                                 + " DELETE FROM %s r" % reftable
                                 + " USING "
                                 + "   (SELECT subject, i2.value" + allsubj_updtrips_query_frag + ') AS i,'
                                 + "   %(table)s AS t"
                                 + " WHERE r.value = t.value AND i.subject = t.subject AND i.value != t.value"
                                 + " RETURNING r.subject"
                                 + ")"
                                 + " INSERT INTO %s" % mtable
                                 + " SELECT DISTINCT d.subject FROM deletions d"
                                 + " LEFT OUTER JOIN %s m ON (d.subject = m.id)" % mtable
                                 + " WHERE m.id IS NULL"
                                 ) % parts
                    #web.debug(reftag, query)
                    self.dbquery(query)

                if reftags:
                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update reftags chased (B)' % (tagdef.tagname, depth))
                    pass

                if flagcol:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT subject' + allsubj_updtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update mutations flagged (B)' % (tagdef.tagname, depth))

                # update triples where graph had a different value than non-null input
                query = ('UPDATE %(table)s AS t SET value = i.value'
                         + ' FROM (SELECT i2.subject, i2.value' + allsubj_updtrips_query_frag + ') AS i'
                         + ' WHERE t.subject = i.subject AND t.value != i.value'
                    ) % parts
                #web.debug(query)
                count += self.dbquery(query)

                #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update mutations applied (B)' % (tagdef.tagname, depth))

            if reftags:
                if not flagcol or not isowncol:
                    # update subject metadata for all implicitly modified subjects
                    for tag, val in [ ('subject last tagged', '%s::timestamptz' % wrapval(nowval)),
                                      ('subject last tagged txid', 'txid_current()') ]:
                        self.set_tag_intable(self.tagdefsdict[tag], mtable,
                                             idcol='id', valcol=val, flagcol=None,
                                             wokcol=None, isowncol=None, test=False,
                                             enforce_tag_authz=False, set_mode='merge', depth=depth+1)

                    self.dbquery('DROP TABLE %s' % mtable)
                else:
                    # we passed modified subject info to caller via intable.flagcol...
                    pass
                

                for reftag in reftags:
                    # update per-referenced tag metadata and subject-tags mappings
                    reftagdef = self.tagdefsdict[reftag]
                    reftable = self.wraptag(reftag)

                    self.set_tag_lastmodified(None, reftagdef)

                    self.delete_tag_intable(self.tagdefsdict['tags present'], 
                                            '(SELECT DISTINCT p.subject FROM "_tags present" p'
                                            + ' LEFT OUTER JOIN %s r ON (p.subject = r.subject)' % reftable
                                            + ' WHERE p.value = %s' % (wrapval(reftagdef.tagname),)
                                            + '   AND r.subject IS NULL) s',
                                            idcol='subject', valcol=wrapval(reftagdef.tagname) + '::text', unnest=False)

                #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update reftag subject metdata updated' % (tagdef.tagname, depth))

            # add input triples not present in graph

            if newcol:
                if flagcol:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT subject' + oldsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT subject' + newsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update inserts flagged' % (tagdef.tagname, depth))

                if tagdef.tagname not in ['tags present', 'id', 'readok', 'writeok']:
                    self.set_tag_intable(self.tagdefsdict['tags present'], 
                                         ('(SELECT DISTINCT subject, False AS created' + oldsubj_newtrips_query_frag + ')'
                                          ) % parts,
                                         idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', test=False,
                                         flagcol=None, wokcol=None, isowncol=None, enforce_tag_authz=False, set_mode='merge', unnest=False, depth=depth+1, wheres=['created = False'], newcol='created')
                    self.set_tag_intable(self.tagdefsdict['tags present'], 
                                         ('(SELECT DISTINCT subject, True AS created' + newsubj_newtrips_query_frag + ')'
                                          ) % parts,
                                         idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', test=False,
                                         flagcol=None, wokcol=None, isowncol=None, enforce_tag_authz=False, set_mode='merge', unnest=False, depth=depth+1, wheres=['created = True'], newcol='created')

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update presence updated' % (tagdef.tagname, depth))

                query = ('INSERT INTO %(table)s (subject, value)'
                         + ' SELECT subject, i2.value' + oldsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query)

                query = ('INSERT INTO %(table)s (subject, value)'
                         + ' SELECT subject, i2.value' + newsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query) 

                #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update inserts performed' % (tagdef.tagname, depth))
            else:
                if flagcol:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT subject' + allsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update inserts flagged(B)' % (tagdef.tagname, depth))

                if tagdef.tagname not in ['tags present', 'id', 'readok', 'writeok']:
                    self.set_tag_intable(self.tagdefsdict['tags present'], 
                                         ('(SELECT subject' + allsubj_newtrips_query_frag + ')'
                                          ) % parts,
                                         idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', test=False,
                                         flagcol=None, wokcol=None, isowncol=None, enforce_tag_authz=False, set_mode='merge', unnest=False, depth=depth+1)

                    #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update presence updated (B)' % (tagdef.tagname, depth))

                query = ('INSERT INTO %(table)s (subject, value)'
                         + ' SELECT subject, i2.value' + allsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query)
                    
                #self.log('TRACE', 'Application.set_tag_intable(%s,d=%d) single-value update inserts performed' % (tagdef.tagname, depth))
        else:
            # empty tags require insert on missing
            
            if set_mode == 'replace':
                raise NotImplementedError()

            # add input triples not present in graph

            # TODO: handle valcol = False by deleting existing tags?

            # old subjects need presence test in existing graph data
            oldsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s AND NOT %(newcol)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject)'
                + '     WHERE t.subject IS NULL AND i2.value'
                )
            # new subjects have all new triples
            newsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s AND %(newcol)s) i2'
                + '     WHERE i2.value'
                )

            # mixed new and old subjects need presence test in existing graph data
            allsubj_newtrips_query_frag = (
                ' FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value'
                + '     FROM %(intable)s i WHERE %(wheres)s) i2'
                + '     LEFT OUTER JOIN %(table)s t USING (subject)'
                + '     WHERE t.subject IS NULL AND i2.value'
                )

            if newcol:
                if flagcol:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT DISTINCT subject' + oldsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' FROM (SELECT DISTINCT subject' + newsubj_newtrips_query_frag + ') t'
                                  + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                  ) % parts)

                if tagdef.tagname not in ['tags present', 'id', 'readok', 'writeok']:
                    self.set_tag_intable(self.tagdefsdict['tags present'], 
                                         ('(SELECT DISTINCT subject, False AS created' + oldsubj_newtrips_query_frag
                                          + ' UNION ALL '
                                          ' SELECT DISTINCT subject, True AS created' + newsubj_newtrips_query_frag + ')'
                                          ) % parts,
                                         idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', unnest=False, enforce_tag_authz=False, depth=depth+1, newcol='created', test=False)

                query = ('INSERT INTO %(table)s (subject)'
                         + ' SELECT subject' + oldsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query)

                query = ('INSERT INTO %(table)s (subject)'
                         + ' SELECT subject' + newsubj_newtrips_query_frag
                         ) % parts
                count += self.dbquery(query)

            else:
                 if flagcol:
                     self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                   + ' FROM (SELECT DISTINCT subject' + allsubj_newtrips_query_frag + ') t'
                                   + ' WHERE i.%(idcol)s = t.subject AND NOT i.%(flagcol)s'
                                   ) % parts)

                 if tagdef.tagname not in ['tags present', 'id', 'readok', 'writeok']:
                     self.set_tag_intable(self.tagdefsdict['tags present'], 
                                          ('(SELECT DISTINCT subject' + allsubj_newtrips_query_frag + ')'
                                           ) % parts,
                                          idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', unnest=False, enforce_tag_authz=False, depth=depth+1, test=False)

                 query = ('INSERT INTO %(table)s (subject)'
                          + ' SELECT subject' + allsubj_newtrips_query_frag
                          ) % parts
                 count += self.dbquery(query)

        if count > 0:
            #web.debug('updating "%s" metadata after %d modified rows' % (tagdef.tagname, count))
            if tagdef.tagname not in [ 'tag last modified', 'tag last modified txid', 'subject last tagged', 'subject last tagged txid' ]:
                self.set_tag_lastmodified(None, tagdef)

            self.accum_table_changes(table, count)

            count = 0

        #self.log('TRACE', 'Application.set_tag_intable("%s", %s, %s, %s) complete' % (tagdef.tagname, idcol, valcol, wheres))

    def delete_tag_intable(self, tagdef, intable, idcol, valcol, unnest=True):
        table = wraptag(tagdef.tagname)
        icols = [ idcol + ' AS subject' ]
        dwheres = [ 'd.subject = i.subject' ]

        if tagdef.dbtype != '' and valcol:
            if tagdef.multivalue and unnest:
                valcol = 'unnest(%s)' % valcol
            icols.append( valcol + ' AS value' )
            dwheres.append( 'd.value = i.value' )

        sql = ('DELETE FROM %(table)s AS d'
               + ' USING (SELECT %(icols)s FROM %(intable)s) i'
               + ' WHERE %(dwheres)s'
               ) % dict(table=table, intable=intable, icols=','.join(icols), dwheres=' AND '.join(dwheres))

        #web.debug(tagdef)
        #traceInChunks(sql)
        self.dbquery(sql)

    def mergepreds(self, predlist, tagdefs=None):
        """Reorganize predlist into a map keyed by tag, listing all preds that constrain each tag.

           Resulting map has a key for each tag referenced in a
           predicate. The keyed list of predicates should then be
           compiled into a conjunction of value constraints on
           that tag.
        """
        if tagdefs == None:
            tagdefs = self.tagdefsdict

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
            # merge all free-text query strings into a single compound query for better indexed query performance
            ts_queries = []
            for p in list(preds):
                if p.op in [ ':word:', ':!word:' ]:
                    preds.remove(p)

                    if len([ v for v in p.vals if hasattr(v, 'is_subquery') ]):
                        raise Conflict(self, 'Sub-queries are not allowed with operator %s.' % pred.op)

                    try:
                        vals = [ '(%s)' % downcast_value('tsword', v) for v in p.vals ]
                    except ValueError, e:
                        raise Conflict(self, data=str(e))

                    if p.op == ':!word:':
                        vals = [ '!%s' % v for v in vals ]

                    ts_queries.append( '(%s)' % '|'.join(vals) )

            if ts_queries:
                preds.append( web.Storage(tag=tag, op=':tsquery:', vals=[ '&'.join(ts_queries) ]) )

            preds.sort(key=lambda p: (p.op, p.vals))

        return pd

    def tagdef_reftags_closure(self, tagdef):
        refs = set()
        def helper(tagname):
            refs.add(tagname)
            td = self.tagdefsdict[tagname]
            for ref in td.reftags:
                helper(ref)
        for ref in tagdef.reftags:
            helper(ref)
        return refs

    def bulk_delete_tags(self, path=None):
        subjpreds, origlistpreds, ordertags = self.path[-1]

        lpreds = self.mergepreds(origlistpreds)
        dtags = set(lpreds.keys())
        dtagdefs = []
        dtqueries = {}

        # screen early for statically forbidden requests or not-found tagdefs
        for tag in dtags:
            try:
                td = self.tagdefsdict[tag]
                dtagdefs.append(td)
            except KeyError:
                raise Conflict(self, 'Tag "%s" not defined on this server.' % tag)

            if td.writeok == False:
                raise Forbidden(self, 'write to tag "%s"' % tag)

        dtable = wraptag(self.request_guid, '', 'tmp_d_')   # all subjects for triple deletion

        # find the path-matching triples and save in temporary table dtable
        dtable_columns = [
            'id int8 PRIMARY KEY',
            'owner text',
            'writeok boolean',
            'modified boolean DEFAULT False'
            ]

        for tagdef in dtagdefs:
            col = '%s %s%s %s' % (wraptag(tagdef.tagname, prefix='d_'), 
                                  {'': 'bool'}.get(tagdef.dbtype, tagdef.dbtype), 
                                  {True:'[]'}.get(tagdef.multivalue, ''),
                                  {True:'UNIQUE'}.get(tagdef.unique, ''))
            dtable_columns.append(col)
            

        self.path[-1] = (subjpreds, origlistpreds + [ web.Storage(tag=tag, op=None, vals=[]) for tag in ['id', 'owner', 'writeok'] ], [])
        dquery, dvalues = self.build_files_by_predlist_path(self.path)
        
        self.dbquery("CREATE TEMPORARY TABLE %s ( %s )" % (dtable, ', '.join(dtable_columns)))
                     
        #self.log('TRACE', 'Application.bulk_delete_tags() after dtable create')

        self.dbquery("INSERT INTO %(dtable)s (%(d_cols)s) SELECT %(cols)s FROM (%(dquery)s) s" 
                     % dict(dtable=dtable, dquery=dquery, 
                            d_cols=', '.join([ 'id', 'owner', 'writeok' ] + [ wraptag(td.tagname, prefix='d_') for td in dtagdefs ]),
                            cols=', '.join([ 'id', 'owner', 'writeok' ] + [ wraptag(td.tagname, prefix='') for td in dtagdefs ]),
                            ), 
                     vars=dvalues)

        #self.log('TRACE', 'Application.bulk_delete_tags() after dtable fill')

        if bool(getParamEnv('bulk tmp analyze', False)):
            self.dbquery('ANALYZE %s' % dtable)

        results = self.dbquery('SELECT True AS found FROM %s LIMIT 1' % dtable)
        if len(results) == 0:
            raise NotFound(self, 'subjects matching subject constraints')

        # first pass: do fine-grained authz and compute affected subjects and tags
        for tagdef in dtagdefs:
            dvalcol = wraptag(tagdef.tagname, prefix='d_')

            # track subjects we'll modify explicitly
            if tagdef.multivalue:
                self.dbquery(("UPDATE %(dtable)s d SET modified = True"
                              + " FROM (SELECT DISTINCT id"
                              + "       FROM (SELECT id, unnest(%(dvalcol)s) AS value FROM %(dtable)s)"
                              + "       WHERE value IS NOT NULL) d2"
                              + " WHERE d.id = d2.id AND NOT d.modified"
                              ) % dict(dtable=dtable, dvalcol=dvalcol),
                             vars=dvalues)
            else:
                self.dbquery(("UPDATE %(dtable)s d SET modified = True"
                              + " FROM %(dtable)s d2"
                              + " WHERE d.id = d2.id AND NOT d.modified AND d2.%(dvalcol)s IS NOT NULL"
                              ) % dict(dtable=dtable, dvalcol=dvalcol),
                             vars=dvalues)

            # find all implicitly mutable tagnames
            reftags = self.tagdef_reftags_closure(tagdef)
            dtags.update(reftags)

            # track subjects we'll modify implicitly
            for reftag in reftags:
                reftagdef = self.tagdefsdict[reftag]

                if tagdef.multivalue:
                    self.dbquery(("UPDATE %(dtable)s d SET modified = True"
                                  + " FROM (SELECT DISTINCT r.subject"
                                  + "       FROM %(reftag)s r"
                                  + "       JOIN (SELECT id, unnest(%(dvalcol)s) AS value FROM %(dtable)s) d2 ON (r.value = d2.value)) r"
                                  + " WHERE d.id = r.subject AND NOT d.modified"
                                  ) % dict(dtable=dtable, dvalcol=dvalcol, reftag=wraptag(reftag)),
                                 vars=dvalues)

                    self.dbquery(("INSERT INTO %(dtable)s (id, modified)"
                                  + " SELECT DISTINCT r.subject, True"
                                  + " FROM %(reftag)s r"
                                  + " JOIN (SELECT id, unnest(%(dvalcol)s) AS value FROM %(dtable)s) d ON (r.value = d.value)"
                                  + " LEFT OUTER JOIN %(dtable)s d2 ON (d2.id = r.subject)"
                                  + " WHERE d2.id IS NULL"
                                  ) % dict(dtable=dtable, dvalcol=dvalcol, reftag=wraptag(reftag)),
                                 vars=dvalues)

                else:
                    self.dbquery(("UPDATE %(dtable)s d SET modified = True"
                                  + " FROM (SELECT DISTINCT r.subject"
                                  + "       FROM %(reftag)s r"
                                  + "       JOIN %(dtable)s d2 ON (r.value = d2.%(dvalcol)s)) r"
                                  + " WHERE d.id = r.subject AND NOT d.modified"
                                  ) % dict(dtable=dtable, dvalcol=dvalcol, reftag=wraptag(reftag)),
                                 vars=dvalues)

                    self.dbquery(("INSERT INTO %(dtable)s (id, modified)"
                                  + " SELECT DISTINCT r.subject, True"
                                  + " FROM %(reftag)s r"
                                  + " JOIN %(dtable)s d ON (r.value = d.%(dvalcol)s)"
                                  + " LEFT OUTER JOIN %(dtable)s d2 ON (d2.id = r.subject)"
                                  + " WHERE d2.id IS NULL"
                                  ) % dict(dtable=dtable, dvalcol=dvalcol, reftag=wraptag(reftag)),
                                 vars=dvalues)

            if tagdef.tagref and (not tagdef.softtagref):
                otagdef = self.tagdefsdict[tagdef.tagref]
                oquery, ovalues = self.build_files_by_predlist_path([(
                            [ web.Storage(tag=tagdef.tagref, op=None, vals=[]) ],
                            [ web.Storage(tag=tag, op=None, vals=[]) for tag in ['id', 'owner', 'writeok', tagdef.tagref] ],
                            []
                            )],
                                                                    values=dvalues,
                                                                    unnest=otagdef.tagname)
                if tagdef.writeok is None:
                    # may need to test permissions on per-object basis for this tag before deleting triples
                    if tagdef.writepolicy in [ 'object', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                        if tagdef.multivalue:
                            results = self.dbquery(('SELECT d.id'
                                                    + ' FROM (SELECT id, unnest(%(dvalcol)s) AS value FROM %(dtable)s) d'
                                                    + ' JOIN (%(oquery)s) o ON (d.value = o.%(tagref)s)'
                                                    + ' WHERE NOT coalesce(o.writeok, False)'
                                                    + ' LIMIT 1'
                                                    ) % dict(dtable=dtable, dvalcol=dvalcol, oquery=oquery, tagref=wraptag(tagdef.tagref, '', '')),
                                                   vars=dvalues)
                        else:
                            results = self.dbquery(('SELECT d.id'
                                                    + ' FROM %(dtable)s d'
                                                    + ' JOIN (%(oquery)s) o ON (d.%(dvalcol)s = o.%(tagref)s)'
                                                    + ' WHERE NOT coalesce(o.writeok, False)'
                                                    + ' LIMIT 1'
                                                    ) % dict(dtable=dtable, dvalcol=dvalcol, oquery=oquery, tagref=wraptag(tagdef.tagref, '', '')),
                                                   vars=dvalues)

                        if len(results) > 0:
                            raise Forbidden(self, 'write to tag "%s" on one or more referenced objects' % tag)

                    if tagdef.writepolicy in [ 'objectowner' ]:
                        if tagdef.multivalue:
                            results = self.dbquery(('SELECT d.id'
                                                    + ' FROM (SELECT id, unnest(%(dvalcol)s) AS value FROM %(dtable)s) d'
                                                    + ' JOIN (%(oquery)s) o ON (d.value = o.%(tagref)s)'
                                                    + ' WHERE NOT coalesce(o.owner = ANY (ARRAY[%(roles)s]), False)'
                                                    + ' LIMIT 1'
                                                    ) % dict(dtable=dtable, dvalcol=dvalcol, oquery=oquery, tagref=wraptag(tagdef.tagref, '', ''),
                                                             roles=','.join([ wrapval(r) for r in self.context.attributes ])),
                                                   vars=dvalues)
                        else:
                            results = self.dbquery(('SELECT d.id'
                                                    + ' FROM %(dtable)s d'
                                                    + ' JOIN (%(oquery)s) o ON (d.%(dvalcol)s = o.%(tagref)s)'
                                                    + ' WHERE NOT coalesce(o.owner = ANY (ARRAY[%(roles)s]), False)'
                                                    + ' LIMIT 1'
                                                    ) % dict(dtable=dtable, dvalcol=dvalcol, oquery=oquery, tagref=wraptag(tagdef.tagref, '', ''),
                                                             roles=','.join([ wrapval(r) for r in self.context.attributes ])),
                                                   vars=dvalues)

                        if len(results) > 0:
                            raise Forbidden(self, 'write to tag "%s" on one or more referenced objects' % tag)
                                                                  
            if td.writeok is None:
                # may need to test permissions on per-subject basis for this tag before deleting triples
                if td.writepolicy in ['subject', 'tagandsubject', 'tagorsubject', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                    if td.multivalue:
                        results = self.dbquery(('SELECT True AS unauthorized'
                                                + ' FROM (SELECT id, writeok, unnest(%(dvalcol)s) AS value FROM %(dtable)s) d'
                                                + ' WHERE NOT coalesce(writeok, False) AND value IS NOT NULL'
                                                + ' LIMIT 1'
                                                ) % dict(dtable=dtable, dvalcol=dvalcol), 
                                               vars=dvalues)
                    else:
                        results = self.dbquery(('SELECT True AS unauthorized'
                                                + ' FROM %(dtable)s d'
                                                + ' WHERE NOT coalesce(writeok, False) AND %(dvalcol)s IS NOT NULL'
                                                + ' LIMIT 1'
                                                ) % dict(dtable=dtable, dvalcol=dvalcol), 
                                               vars=dvalues)
                        
                    if len(results) > 0:
                        raise Forbidden(self, 'write to tag "%s" on one or more subjects' % tagdef.tagname)

                if td.writepolicy in ['subjectowner', 'tagorowner', 'tagandowner' ]:
                    if td.multivalue:
                        results = self.dbquery(('SELECT True AS unauthorized'
                                                + ' FROM (SELECT id, owner, unnest(%(dvalcol)s) AS value FROM %(dtable)s) d'
                                                + ' WHERE NOT coalesce(owner = ANY (ARRAY[%(roles)s]), False) AND value IS NOT NULL'
                                                + ' LIMIT 1'
                                                ) % dict(dtable=dtable, dvalcol=dvalcol, roles=','.join([ wrapval(r) for r in self.context.attributes ])), 
                                               vars=dvalues)
                    else:
                        results = self.dbquery(('SELECT True AS unauthorized'
                                                + ' FROM %(dtable)s d'
                                                + ' WHERE NOT coalesce(owner = ANY (ARRAY[%(roles)s]), False) AND %(dvalcol)s IS NOT NULL'
                                                + ' LIMIT 1'
                                                ) % dict(dtable=dtable, dvalcol=dvalcol, roles=','.join([ wrapval(r) for r in self.context.attributes ])), 
                                               vars=dvalues)

                    if len(results) > 0:
                        raise Forbidden(self, 'write to tag "%s" on one or more subjects' % tag)
            
        results = self.dbquery('SELECT True AS found FROM %s WHERE modified LIMIT 1' % dtable)
        if len(results) == 0:
            raise NotFound(self, "tags matching constraints")
 
        # second pass: remove triples
        for tagdef in dtagdefs:
            self.delete_tag_intable(tagdef, dtable, 'id', wraptag(tagdef.tagname, '', 'd_'))
            
        # third pass: update per-tag metadata based on explicit and implicit changes
        for dtag in dtags:
            self.delete_tag_intable(self.tagdefsdict['tags present'], 
                                    ('(SELECT subject, value'
                                     + ' FROM "_tags present" p'
                                     + ' WHERE p.value = %(tagname)s'
                                     + '   AND (SELECT True FROM %(tagtable)s d WHERE d.subject = p.subject AND %(tagname)s = p.value) IS NULL) s')
                                    % dict(tagname=wrapval(dtag), tagtable=wraptag(dtag)),
                                    idcol='subject', 
                                    valcol=wrapval(dtag) + '::text', unnest=False)
            self.set_tag_lastmodified(None, self.tagdefsdict[dtag])

        # finally: update subject metadata for all modified subjects
        for tag, val in [ ('subject last tagged', '%s::timestamptz' % wrapval('now')),
                          ('subject last tagged txid', 'txid_current()') ]:
            self.set_tag_intable(self.tagdefsdict[tag], dtable,
                                 idcol='id', valcol=val, flagcol=None,
                                 wokcol=None, isowncol=None,
                                 wheres=[ 'modified = True' ],
                                 enforce_tag_authz=False, set_mode='merge', test=False)
            
        
    def bulk_delete_subjects(self, path=None):

        if path == None:
            path = self.path

        if not path:
            path = [ ( [], [], [] ) ]

        spreds, lpreds, otags = path[-1]
        lpreds = [ web.Storage(tag=tag, vals=[], op=None) for tag in [ 'file', 'writeok', 'id' ] ]
        path[-1] = spreds, lpreds, otags

        equery, evalues = self.build_files_by_predlist_path(path)

        etable = wraptag('tmp_e_%s' % self.request_guid, '', '')
        mtable = wraptag('tmp_m_%s' % self.request_guid, '', '')
        mtags = set()

        # save subject-selection results, i.e. subjects we are deleting
        self.dbquery('CREATE TEMPORARY TABLE %(etable)s ( id int8 PRIMARY KEY, file text, writeok boolean )'
                     % dict(etable=etable))
        
        self.dbquery('CREATE TEMPORARY TABLE %(mtable)s ( id int8 PRIMARY KEY )'
                     % dict(mtable=mtable))
        
        self.dbquery(('INSERT INTO %(etable)s (id, writeok)'
                      + ' SELECT e.id, e.writeok'
                      + ' FROM ( %(equery)s ) AS e') % dict(equery=equery, etable=etable),
                     vars=evalues)

        results = self.dbquery('SELECT True AS found FROM %s LIMIT 1' % etable)
        if len(results) == 0:
            raise NotFound(self, 'bulk-delete subjects')

        if bool(getParamEnv('bulk tmp analyze', False)):
            self.dbquery('ANALYZE %s' % etable)

        #self.log('TRACE', value='after deletion subject discovery')

        if self.dbquery('SELECT count(id) AS count FROM %(etable)s AS e WHERE coalesce(NOT e.writeok, True)' % dict(etable=etable),
                        vars=evalues)[0].count > 0:
            raise Forbidden(self, 'delete of one or more matching subjects')

        # find all tags in use by all subjects we are deleting...
        subject_tags = [ r.tagname for r in self.dbquery(('SELECT DISTINCT st.value AS tagname'
                                                          + ' FROM "_tags present" AS st'
                                                          + ' JOIN %(etable)s AS e ON (st.subject = e.id)') % dict(etable=etable)) ]

        # update per-tag metadata and track all subjects whose tags are modified due to cascading tagref deletion
        for tagname in subject_tags:
            tagdef = self.tagdefsdict[tagname]
            self.set_tag_lastmodified(None, tagdef)

            stquery, stvalues = self.build_files_by_predlist_path([ (spreds, [ web.Storage(tag=tag, op=None, vals=[]) for tag in ['id', tagname]], [])],
                                                                  values=evalues,
                                                                  unnest=tagname)
            reftags = self.tagdef_reftags_closure(tagdef)
            mtags.update(reftags)

            for reftag in reftags:
                self.dbquery(('INSERT INTO %(mtable)s (id)'
                              + ' SELECT DISTINCT r.subject FROM (%(stquery)s) s JOIN %(reftable)s r ON (s.%(tagname)s = r.value)'
                              + ' WHERE (SELECT id FROM %(mtable)s m WHERE r.subject = m.id LIMIT 1) IS NULL'
                              + '   AND (SELECT id FROM %(etable)s e WHERE r.subject = e.id LIMIT 1) IS NULL')
                             % dict(mtable=mtable, etable=etable, stquery=stquery, reftable=self.wraptag(reftag), tagname=self.wraptag(tagname, '', '')),
                             vars=evalues)

        #self.log('TRACE', value='after set_tag_lastmodified loop')
        
        # delete all deletion subjects, cascading delete purges all other tables
        # caller must delete returned files after transaction is committed
        results = self.dbquery(('DELETE FROM resources AS d'
                                + ' USING (SELECT e.id, f.value AS file'
                                + '        FROM %(etable)s AS e'
                                + '        LEFT OUTER JOIN "_file" AS f ON (e.id = f.subject)) AS e'
                                + ' WHERE d.subject = e.id'
                                + ' RETURNING e.id AS id, e.file AS file') % dict(etable=etable))

        # finally: update subject metadata for all modified subjects
        for tag, val in [ ('subject last tagged', '%s::timestamptz' % wrapval('now')),
                          ('subject last tagged txid', 'txid_current()') ]:
            self.set_tag_intable(self.tagdefsdict[tag], mtable,
                                 idcol='id', valcol=val, flagcol=None,
                                 wokcol=None, isowncol=None,
                                 enforce_tag_authz=False, set_mode='merge', test=False)

        return results

    def bulk_update_transact(self, subject_iter, path=None, on_missing='create', on_existing='merge', copy_on_write=False, enforce_read_authz=True, enforce_write_authz=True, enforce_path_constraints=False, subject_iter_rewindable=False):
        """Perform efficient bulk-update of tag graph for iterator of subject dictionaries (rows) and query path giving shape of update.

           *NOTE*: This function performs its own top-level transaction control. DO NOT run it inside another transaction body.

           'subject_iter'    is the set of input table rows describing subjects
           
           'path'            query path (default from request context) defines shape of update
                             -- only support 1-length path to start with
                             -- tags in subjpreds are used as primary keys to find existing subjects
                                -- updated or created subjects must match any constraints in subjpreds
                                -- only exact '=' constraints supported to begin with
                             -- tag valss in subjpreds and listpreds are set using values from input table row
                                -- subjpreds tag vals set only during creation
                                -- listpreds tag vals set during creation or update
                             -- input rows must match any constraints in subjpreds and listpreds
                                -- behavior undefined for invalid input
                                -- enforce eventually

           'on_missing'      what to do for input rows without corresponding graph subjects
                             -- 'create' a new subject
                             -- 'ignore' input row
                             -- 'abort' bulk_update process
           
           'on_existing'     what to do for input rows with corresponding graph subjects
                             -- 'merge' input row tag-values on top of existing subject tags
                             -- 'replace' subject tags to match input row's list preds
                             -- 'unbind' unique subject tags from existing subject and then treat by on_missing condition
                             -- 'ignore' input row
                             -- 'abort' bulk_update process

        """
        if path == None:
            path = self.path
        
        spreds, lpreds, otags = path[0]
        if not path or len(path) != 1:
            raise BadRequest(self, 'Bulk update requires a simple path with subject and list predicates.')
            
        if not spreds:
            raise BadRequest(self, 'Bulk update requires at least one tag to be referenced as a subject predicate.')

        if on_missing != 'create' and not lpreds:
            raise BadRequest(self, 'Bulk update requires at least one tag to be referenced as a list predicate.')

        def body1():
            """Validate query path and create unique input table to hold input tuples.

               This body func can be repeated under normal dbtransact() control.
            """

            self.spreds = self.mergepreds(spreds)
            self.lpreds = self.mergepreds(lpreds)

            # pre-evaluate update "shape" requirements
            # tag read authz will be handled by regular path-query in body3
            # tag write authz will be handled by set_tag_intable calls in body3
            got_unique_spred = False
            for tag in self.spreds.keys():
                td = self.tagdefsdict.get(tag)
                if td.unique:
                    got_unique_spred = True

            if on_missing == 'create':
                if len( set(self.config['file write users']).intersection(set(self.context.attributes).union(set('*'))) ) == 0:
                    raise Forbidden(self, 'creation of subjects')

            if got_unique_spred == False:
                raise Conflict(self, 'Bulk update requires at least one unique-identifer tag as a subject predicate.')

            # create a transaction-local temporary table of the right shape for input data
            # -- unique table name in case multiple calls are happening
            self.input_tablename = "input_%s" % self.request_guid
            self.input_created_idxname = "input_%s_created_idx" % self.request_guid

            self.input_column_tds = [ self.tagdefsdict.get(t)
                                      for t in set([ t for t in self.spreds.keys() + self.lpreds.keys() ]) ]

            # remap empty type to boolean type
            # remap multivalue tags to value array
            # 1 column per tag: in_tag
            input_column_defs = [ '%s %s%s %s' % (wraptag(td.tagname, '', 'in_'),
                                                  {'': 'boolean'}.get(td.dbtype, td.dbtype),
                                                  {True: '[]'}.get(td.multivalue, ''),
                                                  {True: 'UNIQUE'}.get(td.unique, ''))
                                  for td in self.input_column_tds ]

            # special columns initialized during JOIN with query result
            # rows resulting in creation of new subjects will get default writeok and is_owner True values
            input_column_defs += [ 'id int8 UNIQUE',
                                   'writeok boolean DEFAULT True', 'is_owner boolean DEFAULT True',
                                   'updated boolean DEFAULT False', 'created boolean DEFAULT False' ]

            self.dbquery('CREATE %s TABLE %s ( %s )' % ((subject_iter == False or subject_iter_rewindable or type(subject_iter) == list) and 'TEMPORARY' or '',
                                                        wraptag(self.input_tablename, '', ''), 
                                                        ','.join(input_column_defs)))
            self.dbquery('CREATE INDEX %s ON %s ( created, updated )' % (wraptag(self.input_created_idxname, '', ''), wraptag(self.input_tablename, '', '')))

            for td in self.input_column_tds:
                if not td.unique and False:
                    self.dbquery('CREATE INDEX %s ON %s ( %s )'
                                 % (wraptag(self.input_tablename, '_td%d_idx' % td.id, ''),
                                    wraptag(self.input_tablename, '', ''),
                                    wraptag(td.tagname, '', 'in_')))

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body1() complete' % (self.input_tablename))

        def body1compensation():
            """Destroy input table created by body1."""
            self.dbquery('DROP TABLE %s' % wraptag(self.input_tablename, '', ''))

        def wrapped_constant(td, v):
            """Return one SQL literal representing values v"""
            if td.dbtype != '':
                param_type = td.dbtype
            else:
                param_type = 'bool'
            if v != None:
                try:
                    if td.multivalue:
                        if type(v) == list:
                            return 'ARRAY[ %s ]::%s[]' % (','.join([ wrapval(v, param_type) for v in v ]), param_type)
                        else:
                            return 'ARRAY[ %s ]::%s[]' % (wrapval(v, param_type), param_type)
                    else:
                        if type(v) == list:
                            if v:
                                return '%s::%s' % (wrapval(v[0], param_type), param_type)
                            else:
                                return 'NULL'
                        else:
                            return '%s::%s' % (wrapval(v, param_type), param_type)
                except ValueError, e:
                    raise Conflict(self, data=str(e))
            else:
                return 'NULL'

        def body2tabular():
            """Load input stream into input table and validate content.

               This body func can run at-most once since it consumes input stream.
            """
            table = wraptag(self.input_tablename, '', '')
            columns = ', '.join([ wraptag(td.tagname, '', 'in_') for td in self.input_column_tds ])
            tuples = []

            def insert_tuples(tuples):
                if tuples:
                    self.dbquery(('INSERT INTO %(table)s ( %(columns)s ) VALUES ' % dict(table=table,columns=columns))
                                 + ','.join(tuples))
            
            if hasattr(subject_iter, 'read'):
                # assume this is the user input stream in CSV format

                # build column list in original URI predlist order, 
                # since self.spreds and self.lpreds may be reordered due to using set operations
                # use each column in order of first appearence in case duplicates are present
                got_cols = set()
                csv_cols = []
                for pred in spreds + lpreds:
                    if pred.tag not in got_cols:
                        csv_cols.append(pred.tag)
                        got_cols.add(pred.tag)
                csv_cols = ', '.join([ wraptag(tag, '', 'in_') for tag in csv_cols ])

                # drill down to psycopg2 cursor's efficient csv input handler
                try:
                    self.db._db_cursor().copy_expert("COPY %(table)s (%(columns)s) FROM STDIN CSV DELIMITER ','"
                                                     % dict(table=table, columns=csv_cols),
                                                     subject_iter,
                                                     int(self.config['chunk bytes']))
                except psycopg2.DataError, ev:
                    # couldn't parse the input CSV
                    m = re.match('(?P<msg>.*)\s*CONTEXT:[\s]*COPY input_[^,]*, line (?P<line>[0-9]*), column in_(?P<column>[^:]*): "(?P<value>.*)"[\s]*', str(ev))
                    if m:
                        msg = 'Bad CSV input for column "%(column)s", line %(line)s, value "%(value)s": %(msg)s' % m.groupdict()
                    else:
                        et, ev, tb = sys.exc_info()
                        web.debug('got exception "%s" peforming CSV copy_from()' % str(ev),
                                  traceback.format_exception(et, ev, tb))
                        msg = 'Unknown error processing CSV input.'
                    raise Conflict(self, msg)
                except:
                    et, ev, tb = sys.exc_info()
                    web.debug('got exception "%s" peforming CSV copy_from()' % str(ev),
                              traceback.format_exception(et, ev, tb))
                    raise
            else:
                # assume this is an iterable subject set
                for subject in subject_iter:
                    values = []

                    # build up execute statement w/ subject values
                    for i in range(0, len(self.input_column_tds)):
                        td = self.input_column_tds[i]
                        v = subject.get(td.tagname, None)
                        values.append( wrapped_constant(td, v) )

                    tuples.append( '( %s )' % (', '.join(values)) )

                    if len(tuples) > 200:
                        insert_tuples(tuples)
                        tuples = []

                insert_tuples(tuples)

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body2() input stored' % (self.input_tablename))

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body2() ID index created' % (self.input_tablename))

            # TODO: test input data against input constraints, aborting on conflict (L)
            # -- test in python during preceding insert loop?  or compile one SQL test?
            # -- until implemented, values out of range may have unexpected, but harmless, results

            return None

        def body3():
            """Perform graph update using input table.

               1. Use a normal query by predlist-path to find existing subjects to outer-join w/ input table
                  a. Using subjpred keys for subject search and join conditions
                  b. Rely on read-authz from normal predlist-path query
               2. (Not implemented) Perform pruning based on optional update modes
               3. Create implied subjects for subset of input rows
                  a. Rows not joined to existing subjects
                  b. Allocate new subject IDs, enforcing create-authz
                  c. Update user-supplied spred columns, enforcing write-authz
                  d. Update provenance columns for created rows
                     -- owner, read users, write users w/ subject-remapping rules
                     -- modified, created, created by, etc.
                  e. Update input table 'created' and 'updated' flag for these rows
               4. Update subject tags based on input table
                  a. Update user-supplied lpred columns, enforcing write-authz
                  b. Update input table 'updated' flag for subjects updated by user-supplied data
                  c. Update provenance columns for 'updated' rows
                     -- subject last tagged, etc.
               5. Update tagdef metadata summarizing column updates (for each column update)
            """
            
            if bool(getParamEnv('bulk tmp analyze', False)):
                self.dbquery('ANALYZE %s' % wraptag(self.input_tablename, '', ''))

            # get policy-remapping info if a rule exists
            remap, dstrole, readusers, writeusers = self.getPolicyRule()
            
            # query result will be table of all readable subjects matching spreds
            # and containing all spred and lpred columns, with array cells for multivalue
            equery, evalues = self.build_files_by_predlist_path([ (spreds,
                                                                   subject_iter != False 
                                                                   and [web.Storage(tag=tag, op=None, vals=[]) for tag in set([ p.tag for p in spreds ] + ['writeok', 'owner', 'id'])]
                                                                   or [web.Storage(tag=tag, op=None, vals=[]) for tag in 'writeok', 'owner', 'id'],
                                                                   []) ],
                                                                enforce_read_authz=enforce_read_authz)

            # we will update the input table from the existing subjects result
            intable = wraptag(self.input_tablename, '', '')

            # get a constant timetamp we can use repeatedly below...
            nowval = downcast_value('timestamptz', datetime.datetime.now(pytz.timezone('UTC')))
            
            # copy subject id and writeok into special columns, and compute is_owner from owner tag
            assigns = [ ('writeok', 'e.writeok'),
                        ('id', 'e.id'),
                        ('is_owner', 'coalesce(e.owner IN (%s), False)' % ','.join([ wrapval(r) for r in self.context.attributes ])) ]

            if subject_iter == False:
                # we're loading subjects for a pattern-based bulk-tag, so need to set static psuedo-input values
                for td in self.input_column_tds:
                    vals = set()
                    if td.tagname in self.lpreds:
                        for pred in self.lpreds[td.tagname]:
                            if pred.op == '=':
                                vals.update(set(pred.vals))
                            elif pred.op == None:
                                pass
                            else:
                                raise BadRequest(self, 'Patterned bulk tag update does not support predicate operator "%s" for list predicates.' % pred.op )

                            assigns.append( (wraptag(td.tagname, '', 'in_'),
                                             wrapped_constant(td, list(vals))) )

                cols = ', '.join([ lhs for lhs, rhs in assigns ])
                vals = ', '.join([ rhs for lhs, rhs in assigns ])
                equery = ('INSERT INTO %(intable)s (%(cols)s) SELECT %(vals)s FROM ( %(equery)s ) AS e' 
                          % dict(intable=intable, cols=cols, vals=vals, equery=equery))
            else:
                # we're joining subjects against input already loaded from client
                # join the subjects table to the input table on all spred tags which are unique 
                wheres = [ '%s = e.%s' % (wraptag(td.tagname, '', "in_"), wraptag(td.tagname, '', ''))
                           for td in [ self.tagdefsdict[tag] for tag in self.spreds.keys() ]
                           if td.unique ]
                wheres = ' AND '.join(wheres)
                assigns = ', '.join([ '%s = %s' % (lhs, rhs) for lhs, rhs in assigns])
                equery = 'UPDATE %(intable)s AS i SET %(assigns)s FROM ( %(equery)s ) AS e WHERE %(wheres)s' % dict(intable=intable, assigns=assigns, equery=equery, wheres=wheres)

            self.dbquery(equery, evalues)

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() subjects joined to input' % (self.input_tablename))

            if False:
                # 2. prune graph based on 'unbind' conditions, tracking set of modified tags (S) (SZ) (LZ) (L)
                # -- delete subjpred tags on subjects mapped to rows?
                # -- what about partial matches, e.g. unique pred collisions not satisfying full subjpreds set?

                # find existing subjects as result into subject-row map (S) (SZ)
                # -- join graph to input table using complex composition of all subjpreds
                # -- repeat operation after graph was pruned above
                
                # test for 'abort' conditions
                # -- on_missing=abort and some rows not mapped
                # -- on_existing=abort and some rows mapped

                # prune input table based on 'ignore' conditions
                # -- delete mapped rows
                pass

            if bool(getParamEnv('bulk tmp analyze', False)):
                self.dbquery('ANALYZE %s' % intable)

            # create subjects based on 'create' conditions and update subject-row map, tracking set of modified tags
            if on_missing == 'create':

                skeys = ', '.join([ 'i.%s AS %s' % (wraptag(tag, '', 'in_'), wraptag(tag, '', 'in_'))
                                    for tag in self.spreds.keys() ])
                
                skeycmps = ' AND '.join([ 'i.%s = n.%s' % (wraptag(tag, '', 'in_'), wraptag(tag, '', 'in_'))
                                          for tag in self.spreds.keys() ])

                # allocate unique subject IDs for all rows missing a subject and initialize special columns
                query = ('UPDATE %(intable)s AS i SET id = n.id, created = True, updated = True'
                         + ' FROM (SELECT NEXTVAL(\'resources_subject_seq\') AS id, %(skeys)s'
                         + '       FROM %(intable)s AS i'
                         + '       WHERE i.id IS NULL) AS n'
                         + ' WHERE %(skeycmps)s') % dict(intable=intable, skeys=skeys, skeycmps=skeycmps)
                #web.debug(query)
                self.dbquery(query)

                if bool(getParamEnv('bulk tmp cluster', False)):
                    clusterindex = self.get_index_name(self.input_tablename, ['id'])
                    self.dbquery('CLUSTER %(intable)s USING %(index)s' % dict(intable=intable, index=wraptag(clusterindex, prefix='')))

                if bool(getParamEnv('bulk tmp analyze', False)):
                    self.dbquery('ANALYZE %s ( id )' % intable)
                self.dbquery('ANALYZE %s ( created, updated )' % intable)

                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() input uniqueness tested' % (self.input_tablename))

                # insert newly allocated subject IDs into subject table
                count = self.dbquery('INSERT INTO resources (subject) SELECT id FROM %(intable)s WHERE created = True'
                                     % dict(intable=intable))

                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() new subjects created' % (self.input_tablename))

                # set regular subject ID tags for newly created rows, enforcing write authz
                for td in self.input_column_tds:
                    if self.spreds.has_key(td.tagname) and not self.lpreds.has_key(td.tagname) and td.tagname not in ['owner', 'read users', 'write users']:
                        self.set_tag_intable(td, intable,
                                             idcol='id', valcol=wraptag(td.tagname, '', 'in_'), flagcol='updated',
                                             wokcol='writeok', isowncol='is_owner', set_mode='merge', wheres=['created = True'], newcol='created', nowval=nowval)

                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() new subject skeys initialized' % (self.input_tablename))

                if remap and dstrole:
                    # use remapped owner
                    owner_val = '%s::text' % wrapval(dstrole)
                elif self.context.client and self.lpreds.has_key('owner'):
                    # use table-supplied in_owner or default self.context.client
                    owner_val = 'CASE WHEN in_owner IS NULL THEN %s::text ELSE in_owner END' % wrapval(self.context.client)
                elif self.context.client:
                    owner_val = '%s::text' % wrapval(self.context.client)
                else:
                    owner_val = 'NULL'

                if remap:
                    # use remapped users lists
                    readusers_val = 'ARRAY[%s]::text[]' % ','.join([ wrapval(r) for r in readusers ])
                    writeusers_val = 'ARRAY[%s]::text[]' % ','.join([ wrapval(r) for r in writeusers ])
                else:
                    # use user-supplied lists if they were included in lpreds, but be safe regarding NULL values
                    if self.lpreds.has_key('read users'):
                        readusers_val = 'CASE WHEN %(acl)s IS NULL THEN ARRAY[]::text[] ELSE %(acl)s END' % dict(acl=wraptag('read users', '', 'in_'))
                    else:
                        readusers_val = 'ARRAY[]::text[]'
                    if self.lpreds.has_key('write users'):
                        writeusers_val = 'CASE WHEN %(acl)s IS NULL THEN ARRAY[]::text[] ELSE %(acl)s END' % dict(acl=wraptag('write users', '', 'in_'))
                    else:
                        writeusers_val = 'ARRAY[]::text[]'

                if self.context.client:
                    mod_val = '%s::text' % wrapval(self.context.client)
                else:
                    mod_val = 'NULL'
                                                                   
                # set subject metadata for newly created subjects
                for tag, val in [ ('owner', owner_val),
                                  ('created', '%s::timestamptz' % wrapval(nowval)),
                                  ('read users', readusers_val),
                                  ('write users', writeusers_val),
                                  ('tags present', 'ARRAY[%s]::text[]' % ','.join([wrapval(t) for t in 'id', 'readok', 'writeok', 'tags present'])) ]:
                    self.set_tag_intable(self.tagdefsdict[tag], intable,
                                         idcol='id', valcol=val, flagcol='updated',
                                         wokcol=None, isowncol='is_owner',
                                         enforce_tag_authz=False, set_mode='merge',
                                         wheres=[ 'created = True' ],
                                         newcol='created',
                                         nowval=nowval)
                    #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() new subject %s initialized' % (self.input_tablename, tag))
                
                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() new subject metadata initialized' % (self.input_tablename))

            elif on_missing == 'ignore':
                self.dbquery('DELETE FROM %(intable)s WHERE id IS NULL' % dict(intable=intable))
            elif len(self.dbquery('SELECT True AS notfound FROM %(intable)s WHERE id IS NULL LIMIT 1' % dict(intable=intable))) > 0:
                raise Conflict(self, 'One or more bulk-update subject(s) not found.')
            else:
                if bool(getParamEnv('bulk tmp cluster', False)):
                    clusterindex = self.get_index_name(self.input_tablename, ['id'])
                    self.dbquery('CLUSTER %(intable)s USING %(index)s' % dict(intable=intable, index=wraptag(clusterindex, prefix='')))

                if bool(getParamEnv('bulk tmp analyze', False)):
                    self.dbquery('ANALYZE %s ( id )' % intable)

            # update graph tags based on input data, tracking set of modified tags
            for td in self.input_column_tds:
                if self.lpreds.has_key(td.tagname):
                    if td.tagname in [ 'owner', 'read users', 'write users' ]:
                        # these were set during create pass, so exclude them here
                        wheres = [ 'created = False' ]
                    else:
                        wheres = []
                    self.set_tag_intable(td, intable,
                                         idcol='id', valcol=wraptag(td.tagname, '', 'in_'), flagcol='updated',
                                         wokcol='writeok', isowncol='is_owner',
                                         set_mode=on_existing,
                                         wheres=wheres,
                                         newcol='created',
                                         nowval=nowval)

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() input tags applied' % (self.input_tablename))
                
            # update subject metadata based on updated flag in each input row
            for tag, val in [ ('subject last tagged', '%s::timestamptz' % wrapval(nowval)),
                              ('subject last tagged txid', 'txid_current()') ]:
                self.set_tag_intable(self.tagdefsdict[tag], intable,
                                     idcol='id', valcol=val, flagcol='updated',
                                     wokcol=None, isowncol='is_owner',
                                     enforce_tag_authz=False, set_mode='merge',
                                     wheres=[ 'updated = True' ],
                                     newcol='created',
                                     nowval=nowval)
                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() subject %s updated' % (self.input_tablename, tag))

            def decode_name(s):
                if s[0:3] == 'in_':
                    return s[3:]
                else:
                    return s

            if bool(getParamEnv('log bulk details', False)):
                results = self.dbquery('SELECT * FROM %s WHERE updated = True' % intable)
                for res in results:
                    if res.created:
                        self.txlog2('CREATE', parts=dict([ (decode_name(k), v) for k, v in res.iteritems()
                                                           if v != None and k not in [ 'updated', 'writeok', 'is_owner', 'created' ] ]))
                    else:
                        self.txlog2('SET', parts=dict([ (decode_name(k), v) for k, v in res.iteritems()
                                                        if v != None and k not in [ 'updated', 'writeok', 'is_owner', 'created' ] ]))

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() subject timestamps updated' % (self.input_tablename))

        if subject_iter == False:
            # run under one unified transaction scoping our temporary table
            def unified_body():
                body1()
                return body3()
            self.dbtransact(unified_body, lambda x: x)
        elif subject_iter_rewindable or type(subject_iter) == list:
            # run under one unified transaction scoping our temporary table
            def unified_body():
                body1()
                if subject_iter_rewindable:
                    subject_iter.seek(0,0)
                body2tabular()
                return body3()
            self.dbtransact(unified_body, lambda x: x)
        else:
            # run multi-phase transaction with non-temporary table
            self.dbtransact(body1, lambda x: x)
            try:
                self.dbtransact(body2tabular, lambda x: x, limit=0) # prevent retry with limit=0
                return self.dbtransact(body3, lambda x: x)
            finally:
                # always clean up input table if we created one successfully in body1
                try:
                    self.dbtransact(body1compensation, lambda x: x)
                except:
                    et, ev, tb = sys.exc_info()
                    web.debug('got exception "%s" peforming body1compensation for %s' % (str(ev), self.input_tablename),
                              traceback.format_exception(et, ev, tb))

    def build_files_by_predlist_path(self, path=None, limit=None, enforce_read_authz=True, tagdefs=None, vprefix='', listas={}, values=None, offset=None, json=False, builtins=False, unnest=None):
        """Build SQL query expression and values map implementing path query.

           'path = []'    equivalent to path = [ ([], [], []) ]

           'path[-1]'     describes final resulting type/structure... 
                          of form [ web.storage{'id'=N, 'list tag 1'=val, 'list tag 2'=[val...]}... ]

           'path[0:-1]'   contextually constraints set of subjects which can be matched by path[-1]

           'path'         defaults to self.path if not supplied
           'tagdefs'      defaults to self.tagdefsdict if not supplied
           'listas'       provides an optional relabeling of list tags (projected result attributes)

           Optional args 'values'used for recursive calls, not client calls.
        """
        if path == None:
            path = self.path

        if not path:
            path = [ ( [], [], [] ) ]

        if tagdefs == None:
            tagdefs = self.tagdefsdict

        if listas == None:
            listas = dict()

        if not values:
            values = Values()

        roles = [ r for r in self.context.attributes ]
        roles.append('*')
        roles = set(roles)
        #rolekeys = ','.join([ '$%s' % values.add(r) for r in roles ])
        rolekeys = ','.join([ wrapval(r, 'text') for r in roles ])

        prohibited = set(listas.itervalues()).intersection(set(['id', 'readok', 'writeok', 'txid', 'owner']))
        if len(prohibited) > 0:
            raise BadRequest(self, 'Use of %s as list tag alias is prohibited.' % ', '.join(['"%s"' % t for t in prohibited]))

        prohibited = set(listas.iterkeys()).intersection(set(['id', 'readok', 'writeok', 'txid', 'owner' ]))
        if len(prohibited) > 0:
            raise BadRequest(self, 'Aliasing of %s is prohibited.' % ', '.join(['"%s"' % t for t in prohibited]))

        rangemode = self.queryopts.get('range', None)
        if rangemode not in [ 'values', 'count', 'values<', 'values>' ]:
            rangemode = None

        def tag_query(tagdef, preds, values, final=True, tprefix='_', spred=False, scalar_subj=None):
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

               scalar_subj:  if not None, must be an alias.column reference
                  and the returned query will be in the form ( q WHERE subject = scalar_subj )
                  to allow the query to be used in a SELECT list
               
               values is used to produce a query parameter mapping
               with keys unique across a set of compiled queries.
            """
            subject_wheres = []

            m = dict(value='', where='', group='', table='%s t' % wraptag(tagdef.tagname), alias=wraptag(tagdef.tagname, prefix=tprefix))
            wheres = []

            # make a copy so we can mutate it safely
            preds = list(preds)

            valcol = 't.value'
            tsvcol = 't.tsv'
            if tagdef.tagname == 'id':
                m['table'] = 'resources t'
                m['value'] = ', subject AS value'
                valcol = 'subject'
            elif tagdef.tagname == 'readok':
                if enforce_read_authz:
                    # subjects are already filtered by elem_query() and all visible subjects are readok=True...
                    m['table'] = '(SELECT subject, True AS value FROM resources) t'
                elif scalar_subj:
                    m['table'] = ('(SELECT %s,' % scalar_subj
                                  + ' (SELECT value IN (%s) FROM _owner WHERE subject = %s)' % (rolekeys, scalar_subj)
                                  + ' OR '
                                  + ' (SELECT value IN (%s) FROM "_read users" WHERE subject = %s)' % (rolekeys, scalar_subj)
                                  + ' AS value) t')
                else:
                    m['table'] = ('(SELECT subject, True AS value'
                                  + ' FROM (SELECT subject FROM _owner WHERE value IN (%s)) o' % rolekeys
                                  + ' FULL OUTER JOIN (SELECT DISTINCT subject FROM "_read users" WHERE value IN (%s)) r' % rolekeys
                                  + '  USING (subject)) t')
                valcol = 'value'
                m['value'] = ', value' 
            elif tagdef.tagname == 'writeok':
                if scalar_subj:
                    m['table'] = ('(SELECT %s,' % scalar_subj
                                  + ' (SELECT value IN (%s) FROM _owner WHERE subject = %s)' % (rolekeys, scalar_subj)
                                  + ' OR '
                                  + ' (SELECT value IN (%s) FROM "_write users" WHERE subject = %s)' % (rolekeys, scalar_subj)
                                  + ' AS value) t')
                else:
                    m['table'] = ('(SELECT subject, True AS value'
                                  + ' FROM (SELECT subject FROM _owner WHERE value IN (%s)) o' % rolekeys
                                  + ' FULL OUTER JOIN (SELECT DISTINCT subject FROM "_write users" WHERE value IN (%s)) w' % rolekeys
                                  + '  USING (subject)) t')
                valcol = 'value'
                m['value'] = ', value' 
            elif tagdef.multivalue and final:
                if unnest == tagdef.tagname:
                    m['value'] = ', value'
                else:
                    m['value'] = ', array_agg(value) AS value'
                    m['group'] = 'GROUP BY subject'
            elif tagdef.dbtype != '':
                if tagdef.dbtype == 'tsvector':
                    m['value'] = ', tsv AS value'
                else:
                    m['value'] = ', value'

            used_not_op = False
            used_other_op = False

            if tagdef.tagref and (not tagdef.softtagref) and enforce_read_authz:
                # add a constraint so that we can only see tags referencing another entry we can see
                reftagdef = tagdefs[tagdef.tagref]
                refvalcol = wraptag(tagdef.tagref, prefix='')
                refpreds = [web.Storage(tag=tagdef.tagref, op=None, vals=[])]
                if tagdef.readpolicy in [ 'objectowner' ]:
                    # need to add object ownership test that is more strict than baseline object readok enforcement
                    refpreds.append( web.Storage(tag='owner', op='=', vals=list(roles)) )
                if reftagdef.multivalue:
                    refvalcol = 'unnest(%s)' % refvalcol
                refquery = "SELECT %s FROM (%s) s" % (
                    refvalcol,
                    self.build_files_by_predlist_path([ (refpreds,
                                                         [web.Storage(tag=tagdef.tagref, op=None, vals=[])],
                                                         []) ],
                                                      enforce_read_authz=enforce_read_authz,
                                                      values=values,
                                                      tagdefs=tagdefs)[0]
                    )
                preds.append( web.Storage(tag=tagdef.tagname, op='IN', vals=refquery) )

            if scalar_subj:
                wheres.append( 'subject = %s' % scalar_subj )

            for pred in preds:
                if tagdef.dbtype in self.opsExcludeTypes.get(pred.op and pred.op or '', []):
                    raise Conflict(self, 'Operator %s not allowed on tag "%s"' % (pred.op, tagdef.tagname))

                if pred.op == ':absent:':
                    used_not_op = True
                else:
                    used_other_op = True

                if pred.op == 'IN':
                    wheres.append( '%s IN (%s)' % (valcol, pred.vals) )
                elif pred.op != ":absent:" and pred.op and pred.vals:
                    if tagdef.dbtype == '':
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
                        vq, vqvalues = self.build_files_by_predlist_path(path, values=values)
                        return 'SELECT %s FROM (%s) AS sq' % (wraptag(projtag, prefix=''), vq)
                        
                    try:
                        vals = [ wrapval(v, tagdef.dbtype, range_extensions=True) 
                                 for v in pred.vals 
                                 if not hasattr(v, 'is_subquery') ]

                    except ValueError, e:
                        raise Conflict(self, data=str(e))
                    vqueries = [ vq_compile(vq) for vq in pred.vals if hasattr(vq, 'is_subquery') ]
                    bounds = [ '(%s::%s, %s::%s)' % (v[0], tagdef.dbtype, v[1], tagdef.dbtype) for v in vals if type(v) == tuple ]

                    if pred.op == ':tsquery:':
                        # mergepreds already downcasted and reduced all free-text queries to a single query
                        constants = [ 'to_tsquery(%s)' % wrapval(pred.vals[0]) ]
                    else:
                        constants = [ '(%s::%s)' % (v, tagdef.dbtype) for v in vals if type(v) != tuple ]

                    clauses = []
                    if constants:
                        if len(constants) > 1:
                            constants = ', '.join(constants)
                            rhs = 'ANY (ARRAY[%s]::%s[])' % (constants, tagdef.dbtype)
                        else:
                            rhs = constants[0]
                        clauses.append( '%s %s %s' % (pred.op == ':tsquery:' and tsvcol or valcol, Application.opsDB[pred.op], rhs) )

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
                    # this tag is statically unreadable for this user, i.e. user roles not in required tag ACL
                    wheres = [ 'False' ]
                elif tagdef.readok == None:
                    # this tag is dynamically unreadable for this user, i.e. depends on subject or object status
                    if tagdef.readpolicy in [ 'subjectowner', 'tagandowner', 'tagorowner' ]:
                        # need to add subject ownership test that is more strict than baseline subject readok enforcement
                        if scalar_subj:
                            wheres.append( 'r.is_owner' )
                        else:
                            wheres.append( '(SELECT value IN (%s) FROM _owner o WHERE o.subject = t.subject)' % rolekeys )
                    # other authz modes need no further tests here:
                    # -- subject readok status enforced by enclosing elem_query
                    # -- object status enforced by value IN subquery predicate injected before processing preds list
                    #    -- object readok enforced by default
                    #    -- object ownership enforced if necessary by extra owner predicate

            w = ' AND '.join([ '(%s)' % w for w in wheres ])
            if w:
                m['where'] = 'WHERE ' + w

            if scalar_subj and not spred:
                if tagdef.dbtype != '':
                    if tagdef.multivalue:
                        q = '(SELECT %(value)s FROM %(table)s %(where)s %(group)s)'
                    else:
                        q = '(SELECT %(value)s FROM %(table)s %(where)s)'
                    m['value'] = m['value'][1:] # strip off leading ',' char
                else:
                    q = '(SELECT subject IS NOT NULL AS value FROM %(table)s %(where)s)'
                return (q % m, [])
            else:
                if tagdef.dbtype != '':
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

        def elem_query(spreds, lpreds, values, final=True, otags=[]):
            """Compile a query finding subjects by spreds and projecting by lpreds.

               final=True means projection is one column per ltag.
               final=False means projection is a single-column UNION of all ltags.

               values is used to produce a query parameter mapping
               with keys unique across a set of compiled queries.
            """
            if final and (not json):
                if builtins:
                    lpreds = lpreds + [ web.storage(tag='readok', op=None, vals=[]),
                                        web.Storage(tag='id', op=None, vals=[]),
                                        web.storage(tag='writeok', op=None, vals=[]),
                                        web.storage(tag='owner', op=None, vals=[])  ]

            if not lpreds:
                raise BadRequest(self, 'A query requires at least one list predicate.')

            spreds = self.mergepreds(spreds, tagdefs)
            lpreds = self.mergepreds(lpreds, tagdefs)
            
            if 'subject text' in spreds:
                self.update_subject_text_tsv()

            subject_wheres = []
            
            for tag, preds in lpreds.items():
                if tag in [ 'id', 'readok', 'writeok', 'owner' ]:
                    if len([ p for p in preds if p.op]) != 0:
                        raise BadRequest(self, 'Tag "%s" cannot be filtered in a list-predicate.' % tag)

            if enforce_read_authz:
                # remodel root resources with authz status in a way that postgres optimizes better
                inner = [ 'resources r' ]
                inner.append( '(SELECT subject FROM _owner WHERE value IN (%s)) is_owner USING (subject)' % rolekeys )
                inner.append( '(SELECT DISTINCT subject FROM "_read users" WHERE value IN (%s)) is_reader USING (subject)' % rolekeys )

                selects = [ 'r.subject AS subject', 
                            'is_owner.subject IS NOT NULL AS is_owner', 
                            'is_reader.subject IS NOT NULL AS is_reader' ]

                inner = [ ('(SELECT '
                           + ', '.join(selects)
                           + ' FROM '
                           + ' LEFT OUTER JOIN '.join(inner)
                           + ') r') ]

                if enforce_read_authz:
                    subject_wheres.append('(r.is_owner OR r.is_reader)')

            else:
                inner = [ 'resources r' ]
            
            selects = []
            outer = []

            for tag, preds in spreds.items():
                sq, swheres = tag_query(tagdefs[tag], preds, values, tprefix='s_', spred=True)
                if swheres:
                    outer.append(sq)
                    subject_wheres.extend(swheres)
                else:
                    inner.append(sq)

            finals = []
            otagexprs = dict()
            for tag, preds in lpreds.items():
                td = tagdefs[tag]

                if td.dbtype == 'tsvector':
                    raise Conflict(self, 'Tag "%s" can only be used in subject predicates, not in list predicates.' % td.tagname)

                if rangemode and final:
                    if len([ p for p in preds if p.op]) > 0:
                        raise BadRequest(self, 'Operators not supported in rangemode list predicates.')
                    if tag == 'id':
                        range_column = 'subject'
                        range_table = 'resources'
                    elif tag in [ 'readok', 'writeok' ]:
                        acl = dict(readok='read', writeok='write')[tag]
                        range_table = 'resources LEFT OUTER JOIN "_%s users" acl USING (subject) LEFT OUTER JOIN "_owner" o USING (subject)' % acl
                        range_column = 'NOT (acl.value IS NULL OR acl.value NOT IN (%(rolekeys)s)) OR NOT (o.value IS NULL OR o.value NOT IN (%(rolekeys)s))' % dict(rolekeys=rolekeys)
                    elif td.dbtype != '':
                        # find active value range for given tag
                        range_column = wraptag(td.tagname) + '.value'
                        range_table = wraptag(td.tagname) + ' JOIN resources USING (subject)'
                    else:
                        # pretend empty tags have binary range True, False
                        range_column = 't.x'
                        range_table = '(VALUES (True), (False)) AS t (x)'
                else:
                    if spreds.has_key(tag) and len([ p for p in preds if p.op != None]) == 0 and not tagdefs[tag].multivalue:
                        # this projection does not further filter triples relative to the spred so optimize it away
                        lq = None
                    else:
                        if rangemode:  
                            lq, swheres = tag_query(td, preds, values, final, tprefix='l_')
                        else:
                            lq, swheres = tag_query(td, preds, values, final, tprefix='l_', scalar_subj='r.subject')
                        if swheres:
                            raise BadRequest(self, 'Operator ":absent:" not supported in projection list predicates.')

                if final:
                    if rangemode == None:
                        # returning triple values per subject
                        if lq:
                            tprefix = None
                            expr = lq
                            #outer.append(lq)
                            #tprefix = 'l_'
                        else:
                            tprefix = 's_'
                            if td.dbtype != '':
                                expr = '%s.value' % wraptag(td.tagname, prefix=tprefix)
                            else:
                                expr = '%s.subject IS NOT NULL' % wraptag(td.tagname, prefix=tprefix)
                    elif rangemode == 'values':
                        # returning distinct values across all subjects
                        expr = '(SELECT array_agg(DISTINCT %s) FROM %s)' % (range_column, range_table)
                    elif rangemode == 'count':
                        # returning count of distinct values across all subjects
                        expr = '(SELECT count(DISTINCT %s) FROM %s)' % (range_column, range_table)
                    else:
                        # returning (in)frequent values
                        if rangemode[-1] == '<':
                            freqorder = 'ASC'
                        else:
                            freqorder = 'DESC'
                        expr = ('(SELECT array_agg(value) '
                                 'FROM (SELECT %(column)s AS value, count(%(column)s) AS count '
                                       'FROM %(table)s '
                                       'GROUP BY %(column)s '
                                       'ORDER BY count %(order)s, value '
                                       '%(limit)s) AS t) '
                                % dict(column=range_column,
                                       table=range_table,
                                       order=freqorder,
                                       limit=({ True: 'LIMIT %d' % (limit != None and limit or 0), False: ''}[limit != None]))
                                )
                    otagexprs[listas.get(td.tagname, td.tagname)] = expr
                    if json:
                        try:
                            selects.append('jsonfield(%s, val2json(%s))' % (wrapval(listas.get(td.tagname, td.tagname)), expr))
                        except ValueError, e:
                            raise Conflict(self, data=str(e))
                    else:
                        selects.append('%s AS %s' % (expr, wraptag(listas.get(td.tagname, td.tagname), prefix='')))
                        
                else:
                    finals.append(lq)

            if not final:
                selects.append( '(%s) AS context' % ' UNION '.join([ 'SELECT * FROM %s s' % sq for sq in finals ]) )

            if subject_wheres:
                where = 'WHERE ' + ' AND '.join([ '(%s)' % w for w in subject_wheres ])
            else:
                where = ''

            tables = [ ' JOIN '.join(inner[0:1] + [ '%s USING (subject)' % i for i in inner[1:] ]) ]
            tables += [ '%s USING (subject)' % o for o in outer ]
            tables = ' LEFT OUTER JOIN '.join(tables)

            if otags and final:
                order = ' ORDER BY %s' % ', '.join([ '%s %s NULLS LAST' % (otagexprs[listas.get(t, t)],
                                                                           { ':asc:': 'ASC', ':desc:': 'DESC', None: 'ASC'}[dir])
                                                     for t, dir in otags])
            else:
                order = ''

            selects = ', '.join([ s for s in selects ])

            if rangemode == None or not final:
                if final and json:
                    selects = 'jsonobj(ARRAY[%s]) AS json' % selects

                q = ('SELECT %(selects)s FROM %(tables)s %(where)s %(order)s' 
                     % dict(selects=selects,
                            tables=tables,
                            where=where,
                            order=order))
            else:
                if json:
                    selects = 'jsonobj(ARRAY[%s]) AS json' % selects

                q = ('WITH resources AS ( SELECT subject FROM %(tables)s %(where)s ) SELECT %(selects)s' 
                     % dict(selects=selects,
                            tables=tables,
                            where=where))
                
            return q

        cq = None
        ordertags=[]
        for i in range(0, len(path)):
            spreds, lpreds, otags = path[i]
            if i > 0:
                cpreds = path[i-1][1]
                tagtypes = set([ tagdefs[pred.tag].dbtype for pred in cpreds ])
                tagrefs = set([ tagdefs[pred.tag].tagref for pred in cpreds if tagdefs[pred.tag].tagref is not None ])
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
                        ordertags = otags

            cq = elem_query(spreds, lpreds, values, i==len(path)-1, otags=ordertags)

        if limit and rangemode == None:
            cq += ' LIMIT %d' % limit

        if offset and rangemode == None:
            cq += ' OFFSET %d' % offset

        def dbquote(s):
            return s.replace("'", "''")
        
        #traceInChunks(cq)
        #web.debug('values', values.pack())

        return (cq, values.pack())


    def build_select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, qd=0, listas=None, tagdefs=None, enforce_read_authz=True, limit=None, listpreds=None, vprefix=''):
        """Backwards compatibility interface, pass to general predlist path function."""

        if subjpreds == None:
            subjpreds = self.subjpreds

        if id != None:
            subjpreds.append( web.Storage(tag='id', op='=', vals=[id]) )

        if listpreds == None:
            if listtags == None:
                listtags = [ x for x in self.select_view()[0]["view tags"] ]
            else:
                listtags = [ x for x in listtags ]

            listpreds = [ web.Storage(tag=tag, op=None, vals=[]) for tag in listtags ]
        else:
            listpreds = [ x for x in listpreds ]

        return self.build_files_by_predlist_path(path=[ (subjpreds, listpreds, ordertags) ], limit=limit, enforce_read_authz=enforce_read_authz, tagdefs=tagdefs, listas=listas)


    def select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, listas=None, tagdefs=None, enforce_read_authz=True, limit=None, listpreds=None):

        query, values = self.build_select_files_by_predlist(subjpreds, listtags, ordertags, id=id, listas=listas, tagdefs=tagdefs, enforce_read_authz=enforce_read_authz, limit=limit, listpreds=None)

        #web.debug(len(query), query, values)
        #web.debug('%s bytes in query:' % len(query))
        #for string in query.split(','):
        #    web.debug (string)
        #web.debug(values)
        #web.debug('...end query')
        #for r in self.dbquery('EXPLAIN ANALYZE %s' % query, vars=values):
        #    web.debug(r)
        return self.dbquery(query, vars=values)

    def select_files_by_predlist_path(self, path=None, limit=None, enforce_read_authz=True, offset=None, json=False):
        #self.txlog('TRACE', value='select_files_by_predlist_path entered')
        query, values = self.build_files_by_predlist_path(path, limit=limit, enforce_read_authz=enforce_read_authz, offset=offset, json=json)
        #self.txlog('TRACE', value='select_files_by_predlist_path query built')
        result = self.dbquery(query, values)
        #self.txlog('TRACE', value='select_files_by_predlist_path exiting')
        return result

    def copyto_csv_files_by_predlist_path(self, outfile, path, limit=None, enforce_read_authz=True, offset=None, json=False):
        #self.txlog('TRACE', value='select_files_by_predlist_path entered')
        spreds, lpreds, otags = path[-1]
        got_cols = set()
        csv_cols = []
        for pred in lpreds:
            if pred.tag not in got_cols:
                csv_cols.append(pred.tag)
                got_cols.add(pred.tag)
        csv_cols = ', '.join([ wraptag(tag, '', '') for tag in csv_cols ])

        query, values = self.build_files_by_predlist_path(path, limit=limit, enforce_read_authz=enforce_read_authz, offset=offset, json=json)
        query = 'SELECT %s FROM (%s) s' % (csv_cols, query)

        self.db._db_cursor().copy_expert("COPY (%s) TO STDOUT CSV DELIMITER ','" % query,
                                         outfile)

        #self.txlog('TRACE', value='select_files_by_predlist_path query built')
        result = self.dbquery(query, values)
        #self.txlog('TRACE', value='select_files_by_predlist_path exiting')
        return result

    def update_subject_text_tsv(self):
        """Find stale subjects and update their "subject text" tsv value to latest graph content.
        """
        stalequery = "SELECT subject FROM %s WHERE value > coalesce(tsv_txid, 0)" % self.wraptag('subject last tagged txid')

        if len(self.dbquery('SELECT True AS value FROM (%s) s LIMIT 1' % stalequery)) == 0:
            # skip expensive work below if nothing is stale... this query is directly supported by a partial value index
            return

        # we only index text tags that are effectively the same read authz as the subjects themselves
        text_tags = [ td.tagname for td in self.tagdefsdict.values() if td.dbtype == 'text' and td.readpolicy in ['anonymous', 'subject', 'tagorsubject'] ]
        
        parts = [ "SELECT subject, tsv FROM %s" % self.wraptag(tagname) for tagname in text_tags ]

        self.dbquery( "WITH stale AS (%s) " % stalequery
                      + " DELETE FROM %s AS st" % self.wraptag('subject text')
                      + " USING stale"
                      + " WHERE st.subject = stale.subject" )

        self.dbquery( "INSERT INTO %s (subject, tsv)" % self.wraptag('subject text')
                      + " SELECT subject, tsv_agg(tsv) AS tsv"
                      + " FROM (%s) documents" % ' UNION ALL '.join(parts)
                      + " JOIN (%s) stale USING (subject)" % stalequery
                      + " GROUP BY SUBJECT" )

        self.set_tag_lastmodified(None, self.tagdefsdict['subject text'])

    def select_predlist_path_txid(self, path=None, limit=None, enforce_read_authz=True):
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
                tags = set(['owner', 'read users'])
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
            return self.dbquery(query, vars=values)[0].txid

        return relevant_tags_txid(path)

    def prepare_path_query(self, path, list_priority=['path', 'list', 'view', 'subject', 'default'], extra_tags=[]):
        """Prepare (path, listtags, writetags, limit) from input path, web environment, and input policies.

           list_priority  -- chooses first successful source of listtags

                'path' : use listpreds from path[-1]
                'list' : use 'list' queryopt
                'view' : use view named by 'view' queryopt
                'subject' : use view named by 'default view' tag of subject ... REQUIRES EXTRA QUERY STEP AND SINGLE SUBJECT
                'default' : use 'default' view
                'all' : use all defined tags

           extra_tags  -- tags to add to listpreds of path[-1] without adding to listtags or writetags."""

        if not path:
            path = [ ( [], [], [] ) ]
        else:
            # shallow copy
            path = [ x for x in path ]

        subjpreds, listpreds, ordertags = path[-1]
        
        unique = self.validate_subjpreds_unique(acceptBlank=True, subjpreds=subjpreds)

        def wrap_results(listtags=None, listpreds=None, writetags=[], ordered=False):
            # build full results tuple from derived listtags or listpreds, reordering a bit if ordered=False
            if listpreds:
                have_tags = set([ p.tag for p in listpreds ])
            else:
                if not listtags:
                    listtags = [ tagdef.tagname for tagdef in self.tagdefsdict.values() ]
                listpreds = [ web.Storage(tag=tag, op=None, vals=[]) for tag in listtags ]
                have_tags = set(listtags)

            listtags = [ p.tag for p in listpreds ]
            listpreds += [ web.Storage(tag=tag, op=None, vals=[]) for tag in extra_tags if tag not in have_tags ]
            have_tags.update( set(extra_tags) )

            if not ordered:
                # apply re-ordering hack
                suffix = [ x for x in [ 'name', 'id' ] if x in have_tags ]
                listpreds_new = [ p for p in listpreds if p.tag not in suffix ]
                for tag in suffix:
                    listpreds_new += [ p for p in listpreds if p.tag == tag ]
                listpreds = listpreds_new

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

            return (path, listtags, writetags, limit, offset)

        # each source-specific function conditionally derives listpreds only if source is present and valid in the request...

        def derive_from_path():
            # derive from query path's listpreds
            if listpreds:
                return wrap_results(listpreds=listpreds, ordered=True)
            return None

        listname = 'view tags'
        writename = 'view tags'

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
            results = self.select_files_by_predlist_path(test_path, limit=1)
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
                          'tagdef readpolicy': validateTagdefPolicy,
                          'tagdef writepolicy': validateTagdefPolicy,
                          'tagdef dbtype': validateTagdefDbtype}

