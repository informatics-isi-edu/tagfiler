
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
                          built_ins=dict(db="tagfiler", 
                                        dbn="postgres", 
                                        dbmaxconnections="8"
                                        )
                          )

webauthn2_config = global_env.get('webauthn2', dict(web_cookie_name='tagfiler'))
webauthn2_config.update(dict(web_cookie_path='/tagfiler'))

webauthn2_manager = Manager(overrides=webauthn2_config)
webauthn2_handler_factory = RestHandlerFactory(manager=webauthn2_manager)

render = None

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
    
    elif dbtype == 'text':
        value = '%s' % value
        if value.find('\00') >= 0:
            raise ValueError('Null bytes not allowed in text value "%s"' % value)
        
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

config_cache = PerUserDbCache('config')
tagdef_cache = PerUserDbCache('tagdef', 'tagname')
typedef_cache = PerUserDbCache('typedef')
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
                                                       web.ctx.ip, ast and ast.context and ast.context.client and u' user=%s' % urllib.quote(ast.context.client) or u'',
                                                       ast and ast.request_guid or u'', desc % data)))
        data = ('%s\n%s' % (status, desc)) % data
        m = re.match('.*MSIE.*',
                     web.ctx.env.get('HTTP_USER_AGENT', 'unknown'))
        if m and False:
            status = '200 OK'
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

daemonuser = getParamEnv('user', 'tagfiler')

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

    def config_filler(self, db):
        self.db = db
        def helper(config):
            config['policy remappings'] = buildPolicyRules(config['policy remappings'])
            return config
        return lambda : [ helper(self.select_config(pred=web.Storage(tag='config', op=None, vals=['tagfiler']))) ]

    def select_config_cached(self, db, configname=None):
        if configname == None:
            configname = 'tagfiler'
        config = config_cache.select(self.db, self.config_filler(db), None, configname)
        if config == None:
            config = config_cache.select(self.db, self.config_filler(db), None, 'tagfiler')
        return config

    def select_config(self, pred=None, params_and_defaults=None, fake_missing=True):
        
        if pred == None:
            pred = web.Storage(tag='config', op='=', vals=['tagfiler'])

        if params_and_defaults == None:
            params_and_defaults = [ ('bugs', None),
                                    ('chunk bytes', 64 * 1024),
                                    ('enabled GUI features', []),
                                    ('file write users', []),
                                    ('help', None),
                                    ('home', 'https://%s' % self.hostname),
                                    ('logo', ''),
                                    ('policy remappings', []),
                                    ('query', None),
                                    ('store path', '/var/www/%s-data' % daemonuser),
                                    ('subtitle', ''),
                                    ('tagdef write users', []),
                                    ('template path', '%s/tagfiler/templates' % distutils.sysconfig.get_python_lib()) ]

        path = [ 
            ( [pred], [web.Storage(tag='config binding', op=None, vals=[])], [] ),
            ( [], [web.Storage(tag=tagname, op=None, vals=[]) for tagname in ['config parameter', 'config value', 'subject last tagged', 'subject last tagged txid']], [] ) 
            ]
        
        query, values = self.build_files_by_predlist_path(path=path,
                                                          tagdefs=Application.static_tagdefs,
                                                          typedefs=Application.static_typedefs)

        config = web.Storage()
        mtimes = []
        txids = []

        for result in self.dbquery(query, values):
            mtimes.append(result['subject last tagged'])
            txids.append(result['subject last tagged txid'])
            config[ result['config parameter'] ] = result['config value']

        config['config'] = 'tagfiler' # BUG: we cannot support config lookup for anything but tagfiler!
        config['subject last tagged'] = max(mtimes)
        config['subject last tagged txid'] = max(txids)

        for key, default in params_and_defaults:
            if type(default) == list:
                config[key] = config.get(key, default)
            else:
                vals = config.get(key, [])
                if len(vals) == 1:
                    config[key] = vals[0]
                else:
                    config[key] = default

        return config

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
                       ('url', 'text', 'URL', None, []),
                       ('id', 'int8', 'Subject ID or subquery', None, []),
                       ('tagpolicy', 'text', 'Tag policy model', None, ['anonymous Any client may access',
                                                                        'subject Subject authorization is observed',
                                                                        'subjectowner Subject owner may access',
                                                                        'object Object authorization is observed',
                                                                        'objectowner Object owner may access',
                                                                        'tag Tag authorization is observed',
                                                                        'tagorsubject Tag or subject authorization is sufficient',
                                                                        'tagandsubject Tag and subject authorization are required',
                                                                        'tagandsubjectandobject Tag, subject, and object authorization are required',
                                                                        'tagorsubjectandobject Either tag or both of subject and object authorization is required',
                                                                        'subjectandobject Subject and object authorization are required',
                                                                        'tagorowner Tag authorization or subject ownership is sufficient',
                                                                        'tagandowner Tag authorization and subject ownership is required',
                                                                        'system No client can access']),
                       ('type', 'text', 'Scalar value type', 'typedef', []),
                       ('tagdef', 'text', 'Tag definition', 'tagdef', []),
                       ('name', 'text', 'Subject name', None, []),
                       ('config', 'text', 'Configuration storage', 'config', []),
                       ('view', 'text', 'View name', 'view', []),
                       ('GUI features', 'text', 'GUI configuration mode', None, ['bulk_value_edit bulk value editing',
                                                                                 'bulk_subject_delete bulk subject delete',
                                                                                 'cell_value_edit cell-based value editing',
                                                                                 'file_download per-row file download',
                                                                                 'subject_delete per-row subject delete',
                                                                                 'view_tags per-row tag page',
                                                                                 'view_URL per-row view URL']) ]:
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
                       ('config binding', 'id', True, 'subject', False),
                       ('config parameter', 'text', False, 'subject', False),
                       ('config value', 'text', True, 'subject', False),
                       ('id', 'int8', False, 'system', True),
                       ('readok', 'boolean', False, 'system', False),
                       ('writeok', 'boolean', False, 'system', False),
                       ('tagdef', 'text', False, 'system', True),
                       ('tagdef type', 'type', False, 'system', False),
                       ('tagdef multivalue', 'boolean', False, 'system', False),
                       ('tagdef active', 'boolean', False, 'system', False),
                       ('tagdef readpolicy', 'tagpolicy', False, 'system', False),
                       ('tagdef writepolicy', 'tagpolicy', False, 'system', False),
                       ('tagdef unique', 'boolean', False, 'system', False),
                       ('tags present', 'tagdef', True, 'system', False),
                       ('tag read users', 'rolepat', True, 'subjectowner', False),
                       ('tag write users', 'rolepat', True, 'subjectowner', False),
                       ('typedef', 'text', False, 'subject', True),
                       ('typedef description', 'text', False, 'subject', False),
                       ('typedef dbtype', 'text', False, 'subject', False),
                       ('typedef values', 'text', True, 'subject', False),
                       ('typedef tagref', 'text', False, 'subject', False),
                       ('read users', 'rolepat', True, 'subjectowner', False),
                       ('write users', 'rolepat', True, 'subjectowner', False),
                       ('owner', 'role', False, 'tagorowner', False),
                       ('modified', 'timestamptz', False, 'system', False),
                       ('subject last tagged', 'timestamptz', False, 'system', False),
                       ('subject last tagged txid', 'int8', False, 'system', False),
                       ('tag last modified', 'timestamptz', False, 'system', False),
                       ('name', 'text', False, 'subjectowner', False),
                       ('view', 'text', False, 'subject', True),
                       ('view tags', 'tagdef', True, 'subject', False) ]:
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
                                          tagwriters=[],
                                          tagref=static_typedefs[typestr].get('typedef tagref')))

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
        global render
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
        self.globals = dict()
        self.globals['context'] = self.context

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
        self.needed_db_globals = [  'typeinfo', 'typesdict', 'tagdefsdict']

        myAppName = os.path.basename(web.ctx.env['SCRIPT_NAME'])

        self.hostname = web.ctx.host

        self.table_changes = {}
        
        self.logmsgs = []
        self.middispatchtime = None

        # BEGIN: get runtime parameters from database
        self.globals['adminrole'] = getParamEnv('admin', 'root')
        self.globals['tagdefsdict'] = Application.static_tagdefs # need these for select_config() below

        #self.log('TRACE', 'Application() constructor after static defaults')

        # get full config
        self.config = self._db_wrapper(lambda db: config_cache.select(db, self.config_filler(db), None, 'tagfiler'))

        #self.log('TRACE', 'Application() self.config loaded')
        del self.globals['tagdefsdict'] # clear this so it will be rebuilt properly during transaction
        
        self.render = web.template.render(self.config['template path'], globals=self.globals)
        render = self.render # HACK: make this available to exception classes too

        # 'globals' are local to this Application instance and also used by its templates
        self.globals['render'] = self.render # HACK: make render available to templates too
        self.globals['urlquote'] = urlquote
        self.globals['idquote'] = idquote
        self.globals['webdebug'] = web.debug
        self.globals['jsonWriter'] = jsonWriter
        self.globals['subject2identifiers'] = lambda subject: self.subject2identifiers(subject)
        self.globals['home'] = self.config.home + web.ctx.homepath
        self.globals['homepath'] = web.ctx.homepath

        # copy many config values to globals map for templates
        self.globals['config'] = self.config
        self.globals['help'] = self.config.help
        self.globals['bugs'] = self.config.bugs
        if self.config.query:
            self.globals['query'] = self.config.query
        else:
            self.globals['query'] = self.globals['home'] + '/query'
        self.globals['subtitle'] = self.config.subtitle
        self.globals['logo'] = self.config.logo
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
        
    def validateTagname(self, tag, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        if tag == '':
            raise Conflict(self, 'You must specify a defined tag name to set values for "%s".' % tagname)
        results = self.select_tagdef(tag)
        if len(results) == 0:
            raise Conflict(self, 'Supplied tag name "%s" is not defined.' % tag)

    def validateTagdefPolicy(self, tag, tagdef=None, subject=None):
        typedef = self.globals['typesdict']['tagpolicy']

        if tagdef and tagdef.tagname == 'tagdef readpolicy':
            # remap read policies to their simplest functional equivalent based on graph ACL enforcement always present for reads
            tag = dict(subject="anonymous",              # subject read enforcement already happens 
                       object="anonymous",               # object read enforcement already happens
                       tagandsubject="tag",              # subject read enforcement already happens
                       tagandsubjectandobject="tag",     # subject and object read enforcement already happens
                       subjectandobject="anonymous")     # subject and object read enforcement already happens

        if tag not in typedef['typedef values']:
            raise Conflict(self, 'Supplied tagdef policy "%s" is not defined.' % tag)

    def validateRole(self, role, tagdef=None, subject=None):
        # TODO: fixme with webauthn2
        pass
                
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
            type = typedef_cache.select(self.db, lambda: self.get_type(), self.context.client, typename)
            if type == None:
                raise Conflict(self, 'The type "%s" is not defined!' % typename)
            dbtype = type['typedef dbtype']
            try:
                key = downcast_value(dbtype, key)
            except ValueError, e:
                raise Conflict(self, data=str(e))

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

    def getPolicyRule(self):
        srcroles = set(self.config['policy remappings'].keys()).intersection(self.context.attributes)

        if len(srcroles) == 1 or self.context.client == None:
            if self.context.client == None:
                # anonymous user, who we represent with empty string key in policy mappings
                # and use a safe default mapping if there is none 
                dstrole, readusers, writeusers, readok, writeok = self.config['policy remappings'].get('', 
                                                                                                       (self.globals['adminrole'], [], [], False, False))
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
                self.delete_tag(newfile, self.globals['tagdefsdict']['read users'])
                for readuser in readusers:
                    self.set_tag(newfile, self.globals['tagdefsdict']['read users'], readuser)
                self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='read users', value=','.join(readusers))
            if writeusers != None:
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
 
    def renderui(self, api, queryopts={}, path=[]):
        self.header('Content-Type', 'text/html')
        self.globals['uiopts'] = {}
        self.globals['uiopts']['api'] = api
        self.globals['uiopts']['queryopts'] = queryopts
        self.globals['uiopts']['path'] = path
        self.globals['uiopts']['help'] = self.globals['help']
        self.globals['uiopts']['bugs'] = self.globals['bugs']
        self.globals['uiopts']['pollmins'] = 1
        return self.render.UI('client')

    def preDispatchFake(self, uri, app):
        self.db = app.db
        self.context = app.context

    def preDispatchCore(self, uri, setcookie=True):
        self.request_uri = uri

        try:
            self.context = self.manager.get_request_context()
        except (ValueError, IndexError):
            # client is unauthenticated but require_client and/or require_attributes is enabled
            acceptType = self.preferredType()
            if acceptType in ['text/html', '*/*']:
                # render a page allowing AJAX login?
                self.login_required = True
            else:
                # give a simple error for non-HTML clients
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
            db_globals_dict = dict(typeinfo=lambda : [ x for x in typedef_cache.select(db, lambda: self.get_type(), self.context.client)],
                                   typesdict=lambda : dict([ (type['typedef'], type) for type in self.globals['typeinfo'] ]),
                                   tagdefsdict=lambda : dict([ (tagdef.tagname, tagdef) for tagdef in tagdef_cache.select(db, lambda: self.select_tagdef(), self.context.client) ]) )

            #self.log('TRACE', value='preparing needed_db_globals')
            for key in self.needed_db_globals:
                if not self.globals.has_key(key):
                    self.globals[key] = db_globals_dict[key]()
                    #self.log('TRACE', value='prepared %s' % key)

            #self.log('TRACE', 'needed_db_globals loaded')
            
            for globalname, default in [ ('view', None),
                                         ('referer', web.ctx.env.get('HTTP_REFERER', None)),
                                         ('tagspace', 'tags'),
                                         ('datapred', self.datapred),
                                         ('dataname', self.dataname),
                                         ('dataid', self.dataid) ]:
                current = self.globals.get(globalname, None)
                if not current:
                    self.globals[globalname] = default

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
                if acceptType in [ 'text/html', '*/*', 'text/uri-list', 'application/x-www-form-urlencoded', 'text/csv', 'application/json', 'text/plain' ]:
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
            tagdef = self.globals['tagdefsdict'].get(pred.tag, None)
            if tagdef == None:
                raise Conflict(self, 'Tag "%s" referenced in subject predicate list is not defined on this server.' % pred.tag)

            if restrictSchema:
                if tagdef.writeok == False:
                    raise Conflict(self, 'Subject predicate sets restricted tag "%s".' % tagdef.tagname)
                if tagdef.typestr == 'empty' and pred.op or \
                       tagdef.typestr != 'empty' and pred.op != '=':
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
            tagdefs = self.globals['tagdefsdict']

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

        if tagdef.tagref:
            reftagdef = tagdefs[tagdef.tagref]
            obj_ok = self.test_tag_authz(mode, None, reftagdef, tagdefs=tagdefs)

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
        for dtype in [ 'tagdef', 'typedef', 'config', 'view', 'file' ] \
                + [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique and tagdef.tagname if tagdef.tagname != 'id' ] \
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
            dbtype = res['typedef dbtype']
            if dbtype == None:
                dbtype = ''
                res['typedef dbtype'] = dbtype
            if res['typedef values'] != None:
                vals = []
                for val in res['typedef values']:
                    key, desc = val.split(" ", 1)
                    key = urlunquote(key)
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

    def insert_file(self, file=None):
        newid = self.dbquery("INSERT INTO resources DEFAULT VALUES RETURNING subject")[0].subject
        subject = web.Storage(id=newid)
        
        self.set_tag_lastmodified(subject, self.globals['tagdefsdict']['id'])

        if file:
            self.set_tag(subject, self.globals['tagdefsdict']['file'], file)

        return newid

    def delete_file(self, subject, allow_tagdef=False):
        wheres = []

        if subject.get('tagdef', None) != None and not allow_tagdef:
            raise Conflict(self, u'Delete of subject tagdef="' + subject.tagdef  + u'" not supported; use dedicated /tagdef/ API.')

        results = self.dbquery('SELECT * FROM "_tags present" WHERE subject = $subject', vars=dict(subject=subject.id))
        for result in results:
            self.set_tag_lastmodified(None, self.globals['tagdefsdict'][result.value])
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

        def augment1(tagdef):
            try:
                typedef = self.globals['typesdict'][tagdef.typestr]
            except:
                typedef = Application.static_typedefs[tagdef.typestr]
             
            tagdef['tagref'] = typedef['typedef tagref']
            tagdef['dbtype'] = typedef['typedef dbtype']

            return tagdef
            
        def augment2(tagdef, tagdefs):
            for mode in ['read', 'write']:
                tagdef['%sok' % mode] = self.test_tag_authz(mode, None, tagdef, tagdefs=tagdefs)

            return tagdef
            
        if tagname:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op='=', vals=[tagname]) ]
        else:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op=None, vals=[]) ]

        results = [ augment1(tagdef) for tagdef in self.select_files_by_predlist(subjpreds, listtags, ordertags, listas=Application.tagdef_listas, tagdefs=Application.static_tagdefs, typedefs=Application.static_typedefs, enforce_read_authz=enforce_read_authz) ]
        results = [ augment2(tagdef, dict([ (res.tagname, res) for res in results ])) for tagdef in results ]

        #web.debug(results)
        return results

    def insert_tagdef(self):
        results = self.select_tagdef(self.tag_id)
        if len(results) > 0:
            raise Conflict(self, 'Tagdef "%s" already exists. Delete it before redefining.' % self.tag_id)

        owner = self.context.client
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

        for tag, value in tags:
            self.set_tag(subject, self.globals['tagdefsdict'][tag], value)

        tagdef = web.Storage([ (Application.tagdef_listas.get(key, key), value) for key, value in tags ])
        tagdef.id = newid
        if owner == None:
            tagdef.owner = None
        tagdef.multivalue = self.multivalue
        tagdef.unique = self.is_unique
        
        self.deploy_tagdef(tagdef)

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
                referenced_tagdef = self.globals['tagdefsdict'].get(tagref, None)

                if referenced_tagdef == None:
                    raise Conflict(self, 'Referenced tag "%s" not found.' % tagref)

                if referenced_tagdef.unique and referenced_tagdef.typestr != 'empty' and referenced_tagdef.tagname not in ['id']:
                    tabledef += ' REFERENCES %s (value) ON DELETE CASCADE' % self.wraptag(tagref)
                
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

        if not tagdef.multivalue:
            clusterindex = self.get_index_name('_' + tagdef.tagname, ['subject'])
        else:
            clusterindex = self.get_index_name('_' + tagdef.tagname, ['subject', 'value'])
        clustercmd = 'CLUSTER %s USING %s' % (self.wraptag(tagdef.tagname), self.wraptag(clusterindex, prefix=''))
        self.dbquery(clustercmd)

    def delete_tagdef(self, tagdef):
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
            self.set_tag_lastmodified(None, self.globals['tagdefsdict']['readok'])
            
        if tagdef.tagname in ['write users', 'owner']:
            self.set_tag_lastmodified(None, self.globals['tagdefsdict']['writeok'])
            

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
                self.delete_tag(subject, self.globals['tagdefsdict']['tags present'], tagdef.tagname)

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
        
        if tagdef.tagname != 'tags present':
            results = self.select_filetags_noauthn(subject, tagdef.tagname)
            if len(results) == 0:
                self.set_tag(subject, self.globals['tagdefsdict']['tags present'], tagdef.tagname)

        self.set_tag_lastmodified(subject, tagdef)
        

    def set_tag_intable(self, tagdef, intable, idcol, valcol, flagcol, wokcol, isowncol, enforce_tag_authz=True, set_mode='merge', unnest=True, wheres=[], test=True):
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
        """
        if len(wheres) == 0:
            # we require a non-empty list for SQL constructs below...
            wheres = [ 'True' ]
        
        if enforce_tag_authz:
            # do the write-authz tests for the active set of intable rows
            if tagdef.writeok == False:
                # tagdef write policy fails statically for this user and tag
                raise Forbidden(self, data='write on tag "%s"' % tagdef.tagname)
            elif tagdef.writeok == None:
                # tagdef write policy depends on per-row information
                if tagdef.writepolicy in [ 'subject', 'tagorsubject', 'tagandsubject', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                    # None means we need subject writeok for this user
                    if self.dbquery('SELECT count(*) AS count FROM %(intable)s WHERE %(wheres)s'
                                    % dict(intable=intable,
                                           wheres=' AND '.join([ '%s = False' % wokcol ] + wheres)))[0].count > 0:
                        raise Forbidden(self, data='write on tag "%s" for one or more matching subjects' % tagdef.tagname)
                if tagdef.writepolicy in [ 'object', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                    # None means we need object writeok for this user
                    # TODO: implement test against objects
                    raise Forbidden(self, data='write on tag "%s" authz not implemented yet' % tagdef.tagname)
                if tagdef.writepolicy in [ 'subjectowner', 'tagorowner', 'tagandowner' ]:
                    # None means we need subject is_owner for this user
                    query = 'SELECT count(*) AS count FROM %(intable)s WHERE %(wheres)s' % dict(intable=intable,
                                                                                                wheres=' AND '.join([ '%s = False' % isowncol ] + wheres))
                    if self.dbquery(query)[0].count > 0:
                        raise Forbidden(self, data='write on tag "%s" for one or more matching subjects' % tagdef.tagname)

                if tagdef.writepolicy in [ 'objectowner' ]:
                    # None meansn we need object is_owner for this user
                    # TODO: implement test against objects
                    raise Forbidden(self, data='write on tag "%s" authz not implemented yet' % tagdef.tagname)
            else:
                # tagdef write policy accepts statically for this user and tag
                pass
            
        table = wraptag(tagdef.tagname)
        count = 0

        if tagdef.tagref:
            # need to validate referential integrity of user input
            targettagdef = self.globals['tagdefsdict'][tagdef.tagref]

            if tagdef.multivalue and unnest:
                refval = 'unnest(%s)' % valcol
            else:
                refval = valcol

            if tagdef.tagref == 'id':
                targetval = 'subject'
                targettable = 'resources'
            elif tagdef.tagref in [ 'readok', 'writeok' ]:
                targetval = 'column1'
                targettable = '(VALUES (True), (False))'
            else:
                targetval = 'value'
                targettable = wraptag(tagdef.tagref)

            undefined = self.dbquery(('SELECT value'
                                           + ' FROM (SELECT %(refval)s AS value FROM %(intable)s s'
                                           + '       EXCEPT'
                                           + '       SELECT %(targetval)s AS value FROM %(targettable)s s) s LIMIT 5')
                                     % dict(refval=refval, intable=intable, targetval=targetval, targettable=targettable))
            if len(undefined) > 0:
                undefined = ','.join([ str(r.value) for r in undefined ])
                raise Conflict(self, 'Provided value or values "%s"=(%s) are not valid references to tag "%s".' % (tagdef.tagname, undefined, tagdef.tagref))

        if tagdef.multivalue:
            # multi-valued tags are straightforward set-algebra on triples
            
            if unnest:
                valcol = 'unnest(%s)' % valcol
            
            if set_mode == 'replace':
                # clear graph triples not present in input
                if flagcol:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' WHERE i.%(idcol)s'
                                  + '       IN'
                                  + '       (SELECT DISTINCT subject'
                                  + '        FROM (SELECT subject, value FROM %(table)s WHERE %(wheres)s'
                                  + '              EXCEPT'
                                  + '              SELECT %(idcol)s AS subject,'
                                  + '                     %(valcol)s AS value'
                                  + '              FROM %(intable)s) AS t)')
                                 % dict(table=table, intable=intable, idcol=idcol, valcol=valcol, flagcol=flagcol,
                                        wheres=' AND '.join(wheres)))

                count += self.dbquery(('DELETE FROM %(table)s AS t'
                                       + ' WHERE ROW(t.subject, t.value)'
                                       + '       NOT IN'
                                       + '       (SELECT %(idcol)s AS subject,'
                                       + '               %(valcol)s AS value'
                                       + '        FROM %(intable)s WHERE %(wheres)s)')
                                      % dict(table=table, intable=intable, idcol=idcol, valcol=valcol,
                                             wheres=' AND '.join(wheres)))

            if test and tagdef.unique:
                # test for uniqueness violations
                if self.dbquery(('SELECT max(count) AS max'
                                 + ' FROM (SELECT count(subject) AS count'
                                 + '       FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value FROM %(intable)s WHERE %(wheres)s'
                                 + '             UNION'
                                 + '             SELECT subject, value FROM %(table)s) AS t'
                                 + '       GROUP BY value) AS t') % dict(intable=intable, table=table, idcol=idcol, valcol=valcol))[0].max > 1:
                    raise Conflict(self, 'Duplicate value violates uniqueness constraint for tag "%s".' % tagdef.tagname)
                #self.log('TRACE', 'Application.set_tag_intable("%s", %s, %s, %s) multival uniqueness tested' % (tagdef.tagname, idcol, valcol, wheres))
                
            # add input triples not present in graph
            if flagcol:
                parts = dict(table=table,
                             intable=intable,
                             idcol=idcol,
                             valcol=valcol,
                             flagcol=flagcol,
                             wheres=' AND '.join(wheres))

                query = ('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                         + ' WHERE i.%(idcol)s'
                         + '       IN'
                         + '       (SELECT DISTINCT subject'
                         + '        FROM (SELECT %(idcol)s AS subject,'
                         + '                     %(valcol)s AS value'
                         + '              FROM %(intable)s WHERE %(wheres)s'
                         + '              EXCEPT'
                         + '              SELECT subject, value FROM %(table)s) AS t)') % parts
                #web.debug(query)
                self.dbquery(query)

            query = ('INSERT INTO %(table)s (subject, value)'
                     + ' SELECT %(idcol)s AS subject,'
                     + '        %(valcol)s AS value'
                     + ' FROM %(intable)s AS i WHERE %(wheres)s'
                     + ' EXCEPT'
                     + ' SELECT subject, value FROM %(table)s'
                     ) % dict(table=table, intable=intable, idcol=idcol, valcol=valcol,
                              wheres=' AND '.join(wheres))
            #web.debug(query)
            count += self.dbquery(query)

        else:
            # single-valued tags require insert-or-update due to cardinality constraint

            incols = [ '%(idcol)s AS subject' % dict(idcol=idcol) ]
            excols = [ 'subject' ]
            
            addwheres = [ '%(idcol)s NOT IN (SELECT subject FROM %(table)s)' % dict(idcol=idcol, table=table) ] + wheres
            updwheres = [ 't.subject = i.subject', '(i.value IS NOT NULL)' ]
            flagwheres = [ '((%s) IS NOT NULL)' % valcol ]

            if tagdef.dbtype != 'empty':
                incols.append( '%(valcol)s AS value' % dict(valcol=valcol) )
                excols.append( 'value' )
                addwheres.append( '((%(valcol)s) IS NOT NULL)' % dict(valcol=valcol) )
                updwheres.append( 'i.value != t.value' )
            else:
                addwheres.append( '((%(valcol)s) = True)' % dict(valcol=valcol) )
                flagwheres.append( '((%(valcol)s) = True)' % dict(valcol=valcol) )

            incols = ', '.join(incols)
            excols = ', '.join(excols)
            addwheres = ' AND '.join(addwheres)

            if tagdef.dbtype != 'empty':
                # input null value represents absence of triples w/ values
                where = '(%s) IS NULL' % valcol
            else:
                # input true value represents presence of pair (predicate typed w/ no object)
                where = '(%s) != True' % valcol
                
            if set_mode == 'replace':
                # remove triples where input lacks them
                if flagcol:
                    self.dbquery(('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                                  + ' WHERE i.%(idcol)s'
                                  + '       IN'
                                  + '       (SELECT subject FROM %(table)s'
                                  + '        EXCEPT'
                                  + '        SELECT %(idcol)s AS subject'
                                  + '        FROM %(intable)s'
                                  + '        WHERE %(wheres)s)')
                                 % dict(table=table, intable=intable,
                                        idcol=idcol, valcol=valcol, flagcol=flagcol,
                                        wheres=' AND '.join(wheres + [ where ])))

                count += self.dbquery(('DELETE FROM %(table)s AS t'
                                       + ' WHERE t.subject'
                                       + '       NOT IN'
                                       + '       (SELECT %(idcol)s AS subject'
                                       + '        FROM %(intable)s'
                                       + '        WHERE %(wheres)s)')
                                      % dict(table=table, intable=intable,
                                             idcol=idcol, valcol=valcol,
                                             wheres=' AND '.join(wheres + [ where ])))
                
            if test and tagdef.unique and tagdef.dbtype != 'empty':
                # test for uniqueness violations
                query = ('SELECT max(count) AS max'
                         + ' FROM (SELECT count(subject) AS count'
                         + '       FROM (SELECT %(idcol)s AS subject, %(valcol)s AS value FROM %(intable)s WHERE %(wheres)s'
                         + '             UNION'
                         + '             SELECT subject, value FROM %(table)s) AS t'
                         + '       GROUP BY value) AS t') % dict(intable=intable, table=table,
                                                                 idcol=idcol, valcol=valcol,
                                                                 wheres='NOT (%s)' % where)
                #web.debug('bulk set unique single-valued tag "%s"' % tagdef.tagname)
                #web.debug(query)
                if self.dbquery(query)[0].max > 1:
                    raise Conflict(self, 'Duplicate value violates uniqueness constraint for tag "%s".' % tagdef.tagname)
                #self.log('TRACE', 'Application.set_tag_intable("%s", %s, %s, %s) uniqueness tested' % (tagdef.tagname, idcol, valcol, wheres))
        
            # track add/update of graph for inequal input triples
            if flagcol:
                query = ('UPDATE %(intable)s AS i SET %(flagcol)s = True'
                         + ' WHERE i.%(idcol)s'
                         + '       IN'
                         + '       (SELECT DISTINCT subject'
                         + '        FROM (SELECT %(incols)s'
                         + '              FROM %(intable)s WHERE %(wheres)s'
                         + '              EXCEPT'
                         + '              SELECT %(excols)s FROM %(table)s) AS t)') % dict(table=table, intable=intable,
                                                                                           idcol=idcol, flagcol=flagcol,
                                                                                           incols=incols, excols=excols,
                                                                                           wheres=' AND '.join(wheres + flagwheres))
                #web.debug(query)
                self.dbquery(query)
                
            # add triples where graph lacked them
            query = ('INSERT INTO %(table)s ( %(excols)s )'
                     + ' SELECT %(incols)s'
                     + ' FROM %(intable)s AS i'
                     + ' WHERE %(addwheres)s') % dict(table=table, intable=intable,
                                                      idcol=idcol, incols=incols, excols=excols,
                                                      addwheres=addwheres)
            #web.debug(query)
            count += self.dbquery(query)

            if tagdef.dbtype != 'empty':
                # update triples where graph had a different value than non-null input
                query = ('UPDATE %(table)s AS t SET value = i.value'
                         + ' FROM (SELECT %(idcol)s AS subject,'
                         + '              %(valcol)s AS value'
                         + '       FROM %(intable)s AS i WHERE %(wheres)s) AS i'
                         + ' WHERE %(updwheres)s') % dict(table=table, intable=intable,
                                                          idcol=idcol, valcol=valcol,
                                                          wheres=' AND '.join(wheres),
                                                          updwheres=' AND '.join(updwheres))
                #web.debug(query)
                count += self.dbquery(query)

        if count > 0:
            #web.debug('updating "%s" metadata after %d modified rows' % (tagdef.tagname, count))
            if tagdef.tagname not in [ 'tag last modified', 'tag last modified txid', 'subject last tagged', 'subject last tagged txid' ]:
                self.set_tag_lastmodified(None, tagdef)

            self.accum_table_changes(table, count)

            count = 0

            # update subject-tags mappings
            if tagdef.tagname not in ['tags present', 'id', 'readok', 'writeok']:
                self.delete_tag_intable(self.globals['tagdefsdict']['tags present'], 
                                        '(SELECT DISTINCT subject FROM "_tags present" WHERE value = %s' % (wrapval(tagdef.tagname),)
                                        + ' EXCEPT SELECT subject FROM %s) s' % table, 
                                        idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', unnest=False)

                self.set_tag_intable(self.globals['tagdefsdict']['tags present'], '(SELECT DISTINCT subject FROM %s)' % table,
                                     idcol='subject', valcol=wrapval(tagdef.tagname) + '::text', 
                                     flagcol=None, wokcol=None, isowncol=None, enforce_tag_authz=False, set_mode='merge', unnest=False)

        #self.log('TRACE', 'Application.set_tag_intable("%s", %s, %s, %s) complete' % (tagdef.tagname, idcol, valcol, wheres))

    def delete_tag_intable(self, tagdef, intable, idcol, valcol, unnest=True):
        table = wraptag(tagdef.tagname)
        dcols = [ 'd.subject' ]
        icols = [ idcol ]

        if valcol:
            if tagdef.multivalue and unnest:
                valcol = 'unnest(%s)' % valcol
            dcols.append( 'd.value' )
            icols.append( valcol )

        sql = (('DELETE FROM %(table)s AS d'
                + ' WHERE ROW( %(dcols)s )'
                + '       IN'
                + '       (SELECT %(icols)s FROM %(intable)s)')
               % dict(table=table, intable=intable, dcols=','.join(dcols), icols=','.join(icols)))

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
            tagdefs = self.globals['tagdefsdict']

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

    def bulk_delete_tags(self, path=None):
        subjpreds, origlistpreds, ordertags = self.path[-1]
        
        unique = self.validate_subjpreds_unique(acceptBlank=True, subjpreds=subjpreds)

        lpreds = self.mergepreds(origlistpreds)
        dtags = lpreds.keys()
        dtagdefs = []

        # screen early for statically forbidden requests or not-found tagdefs
        for tag in dtags:
            try:
                td = self.globals['tagdefsdict'][tag]
                dtagdefs.append(td)
            except KeyError:
                raise Conflict(self, 'Tag "%s" not defined on this server.' % tag)

            if td.writeok == False:
                raise Forbidden(self, 'write to tag "%s"' % tag)

        # topologically sort tagdefs based on tagref linkage
        def td_cmp(td1, td2):
            def ancestors(td):
                a = set()
                while td.tagref:
                    td = self.globals['tagdefsdict'][td.tagref]
                    a.add(td.tagname)
                return a

            if td2.tagname in ancestors(td1):
                return -1
            elif td1.tagname in ancestors(td2):
                return 1
            else:
                return 0

        dtagdefs.sort(cmp=td_cmp)
                
        def coltype(tag):
            td = self.globals['tagdefsdict'][tag]

            if td.multivalue:
                suffix = '[]'
            else:
                suffix = ''

            if td.typestr == 'empty':
                dbtype = 'boolean'
            else:
                dbtype = td.dbtype

            return '%s%s' % (dbtype, suffix)

        # perform deletions in topological order so metadata updates are final including any cascading deletes
        # TODO BUG: what about implicitly deleted tags not part of the client request?
        #   need to invert the tagref graph and anticipate deletes in order to update metadata for those too!
        for td in dtagdefs:
            tag = td.tagname
            tags = ['id', 'owner', 'writeok', tag]

            # build a query matching original subjects plus the extra lpreds constraints for this tag
            tagpath = list(self.path)
            tagpath[-1] = ( subjpreds + lpreds[tag], lpreds[tag] + [web.storage(tag='id', op=None, vals=[])], [] )
            dquery, dvalues = self.build_files_by_predlist_path(tagpath, unnest=tag)
    
            tagpathbrief = list(self.path)
            tagpathbrief[-1] = ( subjpreds, [], [] )
            dquerybrief, dvaluesbrief = self.build_files_by_predlist_path(tagpathbrief)

            if td.writeok == None:
                # need to test permissions on per-subject basis for this tag before deleting triples
                if td.writepolicy in ['subject', 'tagandsubject', 'tagorsubject', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                    count = self.dbquery('SELECT count(*) AS count FROM (%s) s WHERE NOT writeok' % dquerybrief, vars=dvaluesbrief)[0].count
                    if count > 0:
                        raise Forbidden(self, 'write to tag "%s" on one or more subjects' % tag)
                if tagdef.writepolicy in [ 'object', 'subjectandobject', 'tagorsubjectandobject', 'tagandsubjectandobject' ]:
                    # None means we need object writeok for this user
                    # TODO: implement test against objects
                    raise Forbidden(self, data='write on tag "%s" authz not implemented yet' % tagdef.tagname)
                if td.writepolicy in ['subjectowner', 'tagorowner', 'tagandowner' ]:
                    count = self.dbquery(('SELECT count(*) AS count'
                                          + ' FROM ( %(dquery)s ) s'
                                          + ' WHERE NOT CASE'
                                          + '              WHEN ARRAY[ %(roles)s ]::text[] @> ARRAY[ owner ]::text[] THEN True'
                                          + '              ELSE False'
                                          + '           END')
                                         % dict(dquery=dquerybrief,
                                                roles=','.join([ wrapval(r) for r in self.context.attributes ])),
                                         vars=dvaluesbrief)[0].count
                    if count > 0:
                        raise Forbidden(self, 'write to tag "%s" on one or more subjects' % tag)
                if tagdef.writepolicy in [ 'objectowner' ]:
                    # None meansn we need object is_owner for this user
                    # TODO: implement test against objects
                    raise Forbidden(self, data='write on tag "%s" authz not implemented yet' % tagdef.tagname)

            # delete tuples from graph and update metadata
            self.delete_tag_intable(td, '(%s) s' % dquery, 'id', wraptag(tag, '', ''), unnest=False)

            self.delete_tag_intable(self.globals['tagdefsdict']['tags present'], 
                                    ('(SELECT subject, value'
                                     + ' FROM "_tags present" p'
                                     + ' WHERE p.value = %(tagname)s'
                                     + ' EXCEPT SELECT subject, %(tagname)s FROM %(tagtable)s) s')
                                    % dict(tagname=wrapval(tag), tagtable=wraptag(tag)),
                                    idcol='subject', 
                                    valcol=wrapval(tag) + '::text', unnest=False)

            for tag, val in [ ('subject last tagged', '%s::timestamptz' % wrapval('now')),
                              ('subject last tagged txid', 'txid_current()') ]:
                self.set_tag_intable(self.globals['tagdefsdict'][tag], '(%s)' % dquerybrief,
                                     idcol='id', valcol=val, flagcol=None,
                                     wokcol='dummy', isowncol='dummy',
                                     enforce_tag_authz=False, set_mode='merge')

            self.set_tag_lastmodified(None, td)

    def bulk_delete_subjects(self, path=None):

        if path == None:
            path = self.path

        if not path:
            path = [ ( [], [], [] ) ]

        spreds, lpreds, otags = path[-1]
        lpreds = [ web.Storage(tag=tag, vals=[], op=None) for tag in [ 'file' ] ]
        path[-1] = spreds, lpreds, otags

        equery, evalues = self.build_files_by_predlist_path(path)

        etable = wraptag('tmp_e_%s' % self.request_guid, '', '')

        # save subject-selection results, i.e. subjects we are deleting
        self.dbquery('CREATE TEMPORARY TABLE %(etable)s ( id int8, file text, writeok boolean )'
                     % dict(etable=etable))
        
        self.dbquery(('INSERT INTO %(etable)s (id, writeok)'
                      + ' SELECT e.id, e.writeok'
                      + ' FROM ( %(equery)s ) AS e') % dict(equery=equery, etable=etable),
                     vars=evalues)

        if bool(getParamEnv('bulk tmp index', False)):
            self.dbquery('CREATE INDEX %(index)s ON %(etable)s (id)'
                         % dict(etable=etable, index=wraptag('tmp_e_%s_id_idx' % self.request_guid, '', '')))
        
        if bool(getParamEnv('bulk tmp analyze', False)):
            self.dbquery('ANALYZE %s' % etable)

        #self.log('TRACE', value='after deletion subject discovery')

        if self.dbquery('SELECT count(id) AS count FROM %(etable)s AS e WHERE e.writeok = False' % dict(etable=etable),
                        vars=evalues)[0].count > 0:
            raise Forbidden(self, 'delete of one or more matching subjects')

        # TODO: deletion of tuples MAY expand effect into other tables and subjects due to cascading delete...
        #       need to update metadata on tagdefs and/or subjects in those cases too?

        # update tagdef metadata for all tags which will lose tuples due to subject deletion
        subject_tags = [ r for r in self.dbquery(('SELECT DISTINCT st.value AS tagname'
                                                 + ' FROM "_tags present" AS st'
                                                 + ' JOIN %(etable)s AS e ON (st.subject = e.id)') % dict(etable=etable)) ]
        for r in subject_tags:
            self.set_tag_lastmodified(None, self.globals['tagdefsdict'][r.tagname])

        #self.log('TRACE', value='after set_tag_lastmodified loop')
        
        # delete all deletion subjects, cascading delete purges all other tables
        # caller must delete returned files after transaction is committed
        results = self.dbquery(('DELETE FROM resources AS d'
                                + ' USING (SELECT e.id, f.value AS file'
                                + '        FROM %(etable)s AS e'
                                + '        LEFT OUTER JOIN "_file" AS f ON (e.id = f.subject)) AS e'
                                + ' WHERE d.subject = e.id'
                                + ' RETURNING e.id AS id, e.file AS file') % dict(etable=etable))
        self.accum_table_changes('"resources"', len(results))

        return results

    def bulk_update_transact(self, subject_iter, path=None, on_missing='create', on_existing='merge', copy_on_write=False, enforce_read_authz=True, enforce_write_authz=True, enforce_path_constraints=False):
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
                td = self.globals['tagdefsdict'].get(tag)
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

            self.input_column_tds = [ self.globals['tagdefsdict'].get(t)
                                      for t in set([ t for t in self.spreds.keys() + self.lpreds.keys() ]) ]

            # remap empty type to boolean type
            # remap multivalue tags to value array
            # 1 column per tag: in_tag
            input_column_defs = [ '%s %s%s' % (wraptag(td.tagname, '', 'in_'),
                                               (lambda dbtype: {'empty': 'boolean'}.get(dbtype, dbtype))(td.dbtype),
                                               (lambda multival: {True: '[]'}.get(multival, ''))(td.multivalue))
                                  for td in self.input_column_tds ]

            # special columns initialized during JOIN with query result
            # rows resulting in creation of new subjects will get default writeok and is_owner True values
            input_column_defs += [ 'id int8',
                                   'writeok boolean DEFAULT True', 'is_owner boolean DEFAULT True',
                                   'updated boolean DEFAULT False', 'created boolean DEFAULT False' ]

            self.dbquery('CREATE %s TABLE %s ( %s )' % (subject_iter == False and 'TEMPORARY' or '',
                                                        wraptag(self.input_tablename, '', ''), 
                                                        ','.join(input_column_defs)))

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body1() complete' % (self.input_tablename))

        def body1compensation():
            """Destroy input table created by body1."""
            self.dbquery('DROP TABLE %s' % wraptag(self.input_tablename, '', ''))

        def wrapped_constant(td, v):
            """Return one SQL literal representing values v"""
            if td.typestr != 'empty':
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

            if bool(getParamEnv('bulk tmp index', False)):
                self.dbquery('CREATE INDEX %(index)s ON %(intable)s ( id )' % dict(index=wraptag(self.input_tablename, '_id_idx', ''),
                                                                                   intable=wraptag(self.input_tablename, '', '')))
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
                                                                   and [web.Storage(tag=tag, op=None, vals=[]) for tag in set([ p.tag for p in spreds ])]
                                                                   or [],
                                                                   []) ],
                                                                enforce_read_authz=enforce_read_authz)

            # we will update the input table from the existing subjects result
            intable = wraptag(self.input_tablename, '', '')
            
            # copy subject id and writeok into special columns, and compute is_owner from owner tag
            assigns = [ ('writeok', 'e.writeok'),
                        ('id', 'e.id'),
                        ('is_owner', 'CASE WHEN ARRAY[ %s ]::text[] @> ARRAY[ e.owner ]::text[] THEN True ELSE False END' % ','.join([ wrapval(r) for r in self.context.attributes ])) ]

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
                           for td in [ self.globals['tagdefsdict'][tag] for tag in self.spreds.keys() ]
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

                inits = ', '.join(['id = n.id', 'created = True'])

                # allocate unique subject IDs for all rows missing a subject and initialize special columns
                query = ('UPDATE %(intable)s AS i SET %(inits)s'
                         + ' FROM (SELECT NEXTVAL(\'resources_subject_seq\') AS id, %(skeys)s'
                         + '       FROM %(intable)s AS i'
                         + '       WHERE i.id IS NULL) AS n'
                         + ' WHERE %(skeycmps)s') % dict(intable=intable, skeys=skeys, skeycmps=skeycmps, inits=inits)
                #web.debug(query)
                self.dbquery(query)

                if bool(getParamEnv('bulk tmp index', False)) and bool(getParamEnv('bulk tmp cluster', False)):
                    clusterindex = self.get_index_name(self.input_tablename, ['id'])
                    self.dbquery('CLUSTER %(intable)s USING %(index)s' % dict(intable=intable, index=wraptag(clusterindex, prefix='')))

                if bool(getParamEnv('bulk tmp analyze', False)):
                    self.dbquery('ANALYZE %s ( id )' % intable)

                # do this test after cluster/analyze so it is faster
                if self.dbquery('SELECT max(count) AS max FROM (SELECT count(*) AS count FROM %s GROUP BY id) AS t' % intable)[0].max > 1:
                    raise Conflict(self, 'Duplicate input rows violate unique subject key constraint.')

                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() input uniqueness tested' % (self.input_tablename))

                # insert newly allocated subject IDs into subject table
                count = self.dbquery('INSERT INTO resources (subject) SELECT id FROM %(intable)s WHERE created = True'
                                     % dict(intable=intable))

                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() new subjects created' % (self.input_tablename))

                # set regular subject ID tags for newly created rows, enforcing write authz
                for td in self.input_column_tds:
                    if self.spreds.has_key(td.tagname):
                        self.set_tag_intable(td, intable,
                                             idcol='id', valcol=wraptag(td.tagname, '', 'in_'), flagcol='updated',
                                             wokcol='writeok', isowncol='is_owner', set_mode='merge')

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
                                  ('created', '%s::timestamptz' % wrapval('now')),
                                  ('modified', '%s::timestamptz' % wrapval('now')),
                                  ('modified by', mod_val),
                                  ('read users', readusers_val),
                                  ('write users', writeusers_val),
                                  ('tags present', 'ARRAY[%s]::text[]' % ','.join([wrapval(t) for t in 'id', 'readok', 'writeok', 'tags present'])) ]:
                    self.set_tag_intable(self.globals['tagdefsdict'][tag], intable,
                                         idcol='id', valcol=val, flagcol='updated',
                                         wokcol='writeok', isowncol='is_owner',
                                         enforce_tag_authz=False, set_mode='merge',
                                         wheres=[ 'created = True' ])
                
                #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() new subject metadata initialized' % (self.input_tablename))

            elif on_missing == 'ignore':
                self.dbquery('DELETE FROM %(intable)s WHERE id IS NULL' % dict(intable=intable))
            elif self.dbquery('SELECT count(*) AS count FROM %(intable)s WHERE id IS NULL' % dict(intable=intable))[0].count > 0:
                raise NotFound(self, 'bulk-update subject(s)')
            else:
                if bool(getParamEnv('bulk tmp index', False)) and bool(getParamEnv('bulk tmp cluster', False)):
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
                                         wheres=wheres)

            #self.log('TRACE', 'Application.bulk_update_transact(%s).body3() input tags applied' % (self.input_tablename))
                
            # update subject metadata based on updated flag in each input row
            for tag, val in [ ('subject last tagged', '%s::timestamptz' % wrapval('now')),
                              ('subject last tagged txid', 'txid_current()') ]:
                self.set_tag_intable(self.globals['tagdefsdict'][tag], intable,
                                     idcol='id', valcol=val, flagcol=None,
                                     wokcol='writeok', isowncol='is_owner',
                                     enforce_tag_authz=False, set_mode='merge',
                                     wheres=[ 'updated = True' ])

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

    def build_files_by_predlist_path(self, path=None, limit=None, enforce_read_authz=True, tagdefs=None, typedefs=None, vprefix='', listas={}, values=None, offset=None, json=False, builtins=True, unnest=None):
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
            extra_tag_columns = set()

            # make a copy so we can mutate it safely
            preds = list(preds)

            valcol = '%s.value'  % wraptag(tagdef.tagname)
            if tagdef.tagname == 'id':
                m['table'] = 'resources'
                m['value'] = ', subject AS value'
                valcol = 'subject'
            elif tagdef.tagname == 'readok':
                m['table'] = ('(SELECT subject, True AS value FROM _owner WHERE value IN (%s) ' % rolekeys
                              + ' UNION '
                              + 'SELECT subject, True AS value FROM "_read users" WHERE value IN (%s)) s' % rolekeys)
                valcol = 'value'
                m['value'] = ', value' 
            elif tagdef.tagname == 'writeok':
                m['table'] = ('(SELECT subject, True AS value FROM _owner WHERE value IN (%s) ' % rolekeys
                              + ' UNION '
                              + 'SELECT subject, True AS value FROM "_write users" WHERE value IN (%s)) s' % rolekeys)
                valcol = 'value'
                m['value'] = ', value' 
            elif tagdef.multivalue and final:
                if unnest == tagdef.tagname:
                    m['value'] = ', %s.value AS value' % wraptag(tagdef.tagname)
                else:
                    m['value'] = ', array_agg(%s.value) AS value' % wraptag(tagdef.tagname)
                    m['group'] = 'GROUP BY subject'
            elif tagdef.typestr != 'empty':
                m['value'] = ', %s.value AS value' % wraptag(tagdef.tagname)

            used_not_op = False
            used_other_op = False

            if tagdef.tagref and enforce_read_authz:
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
                    self.build_files_by_predlist_path([ ([web.Storage(tag=tagdef.tagref, op=None, vals=[])],
                                                         [web.Storage(tag=tagdef.tagref, op=None, vals=[])],
                                                         []) ],
                                                      values=values,
                                                      tagdefs=tagdefs,
                                                      typedefs=typedefs)[0]
                    )
                preds.append( web.Storage(tag=tagdef.tagname, op='IN', vals=refquery) )

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
                        vq, vqvalues = self.build_files_by_predlist_path(path, values=values)
                        return 'SELECT %s FROM (%s) AS sq' % (wraptag(projtag, prefix=''), vq)
                        
                    try:
                        vals = [ wrapval(v, tagdef.dbtype, range_extensions=True) for v in pred.vals if not hasattr(v, 'is_subquery') ]
                    except ValueError, e:
                        raise Conflict(self, data=str(e))
                    vqueries = [ vq_compile(vq) for vq in pred.vals if hasattr(vq, 'is_subquery') ]
                    constants = [ '(%s::%s)' % (v, tagdef.dbtype) for v in vals if type(v) != tuple ]
                    bounds = [ '(%s::%s, %s::%s)' % (v[0], tagdef.dbtype, v[1], tagdef.dbtype) for v in vals if type(v) == tuple ]

                    clauses = []
                    if constants:
                        constants = ', '.join(constants)
                        clauses.append( '%s %s ANY (ARRAY[%s]::%s[])'
                                        %  (valcol, Application.opsDB[pred.op], constants, tagdef.dbtype) )

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
                        m['table'] += ' JOIN (SELECT subject FROM _owner WHERE value IN (%s)) is_sowner USING (subject)' % rolekeys
                    # other authz modes need no further tests here:
                    # -- subject readok status enforced by enclosing elem_query
                    # -- object status enforced by value IN subquery predicate injected before processing preds list
                    #    -- object readok enforced by default
                    #    -- object ownership enforced if necessary by extra owner predicate

            for tag in extra_tag_columns:
                m['table'] += ' LEFT OUTER JOIN %s USING (subject)' % wraptag(tag)

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

        def elem_query(spreds, lpreds, values, final=True, otags=[]):
            """Compile a query finding subjects by spreds and projecting by lpreds.

               final=True means projection is one column per ltag.
               final=False means projection is a single-column UNION of all ltags.

               values is used to produce a query parameter mapping
               with keys unique across a set of compiled queries.
            """
            if final and (not json) and builtins:
                lpreds = lpreds + [ web.storage(tag='readok', op=None, vals=[]),
                                    web.storage(tag='writeok', op=None, vals=[]),
                                    web.storage(tag='owner', op=None, vals=[]) ]
                if 'id' not in lpreds:
                    lpreds.append( web.Storage(tag='id', op=None, vals=[]) )

            if enforce_read_authz and final and not json:
                spreds = spreds + [ web.Storage(tag='readok', op='=', vals=[True]) ]
                
            spreds = self.mergepreds(spreds, tagdefs)
            lpreds = self.mergepreds(lpreds, tagdefs)
            
            subject_wheres = []
            
            for tag, preds in lpreds.items():
                if tag in [ 'id', 'readok', 'writeok', 'owner' ]:
                    if len([ p for p in preds if p.op]) != 0:
                        raise BadRequest(self, 'Tag "%s" cannot be filtered in a list-predicate.' % tag)

            selects = []
            inner = []
            outer = []

            for tag, preds in spreds.items():
                sq, swheres = tag_query(tagdefs[tag], preds, values, tprefix='s_', spred=True)
                if swheres:
                    outer.append(sq)
                    subject_wheres.extend(swheres)
                else:
                    inner.append(sq)

            if enforce_read_authz and json or not final:
                outer.append( '(SELECT subject FROM "_owner" WHERE value IN (%(rolekeys)s)) AS o' % dict(rolekeys=rolekeys) )
                outer.append( '(SELECT DISTINCT subject FROM "_read users" WHERE value IN (%(rolekeys)s)) AS ru' % dict(rolekeys=rolekeys) )
                subject_wheres.append( 'o.subject IS NOT NULL OR ru.subject IS NOT NULL' )

            finals = []
            otagexprs = dict()
            for tag, preds in lpreds.items():
                td = tagdefs[tag]
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
                    elif td.typestr != 'empty':
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
                outer.append( '(%s) AS context' % ' UNION '.join([ sq for sq in finals ]) )
                selects.append('context.value AS context')

            if subject_wheres:
                where = 'WHERE ' + ' AND '.join([ '(%s)' % w for w in subject_wheres ])
            else:
                where = ''

            if len(inner) == 0:
                tables = [ 'resources AS r' ]
            else:
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
                tagtypes = set([ tagdefs[pred.tag].typestr for pred in cpreds ])
                tagrefs = set([ typedefs[t]['typedef tagref'] for t in tagtypes if typedefs[t]['typedef tagref'] is not None ])
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


    def build_select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, qd=0, listas=None, tagdefs=None, typedefs=None, enforce_read_authz=True, limit=None, listpreds=None, vprefix=''):
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

        return self.build_files_by_predlist_path(path=[ (subjpreds, listpreds, ordertags) ], limit=limit, enforce_read_authz=enforce_read_authz, tagdefs=tagdefs, typedefs=typedefs, listas=listas)


    def select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, listas=None, tagdefs=None, typedefs=None, enforce_read_authz=True, limit=None, listpreds=None):

        query, values = self.build_select_files_by_predlist(subjpreds, listtags, ordertags, id=id, listas=listas, tagdefs=tagdefs, typedefs=typedefs, enforce_read_authz=enforce_read_authz, limit=limit, listpreds=None)

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
            return max(self.dbquery(query, vars=values)[0].txid, self.config['subject last tagged txid'])

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
                    listtags = [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() ]
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
                          'typedef values' : validateEnumeration,
                          'tagdef readpolicy': validateTagdefPolicy,
                          'tagdef writepolicy': validateTagdefPolicy }

    tagtypeValidators = { 'tagname' : validateTagname,
                          'id' : validateSubjectQuery }
