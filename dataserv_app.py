
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
            #  identifying tag (tracked as "tag last modified" on its tagdef
            #  individual subjects (tracked as "subject last tagged" on each identified subject
            results = db.query('SELECT max(txid) AS txid FROM ('
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

            #web.debug(self.cache)
            #web.debug('DbCache: filled %s cache txid = %s' % (self.idtagname, self.fill_txid))
            
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
elif hasattr(json, 'dumps'):
    jsonWriter = json.dumps
else:
    raise RuntimeError(ast=None, data='Could not configure JSON library.')

def urlquote(url, safe=""):
    "define common URL quote mechanism for registry URL value embeddings"
    if type(url) not in [ str, unicode ]:
        url = str(url)
    if type(url) == str:
        url = unicode(url, 'utf8')
    return urllib.quote(url, safe=safe)

def urlunquote(url):
    if type(url) not in [ str, unicode ]:
        url = str(url)
    url = urllib.unquote_plus(url)
    if type(url) == str:
        url = unicode(url, 'utf8')
    elif type(url) == unicode:
        pass
    else:
        raise RuntimeError('unexpected decode type %s in urlunquote()' % type(url))
    return url

def parseBoolString(theString):
    if theString.lower() in [ 'true', 't', 'yes', 'y' ]:
        return True
    else:
        return False

def predlist_linearize(predlist, quotefunc=urlquote):
    def pred_linearize(pred):
        vals = [ quotefunc(val) for val in pred.vals ]
        vals.sort()
        vals = ','.join(vals)
        if pred.op:
            return '%s%s%s' % (quotefunc(pred.tag), pred.op, vals)
        else:
            return '%s' % (quotefunc(pred.tag))
    predlist = [ pred_linearize(pred) for pred in predlist ]
    predlist.sort()
    return ';'.join(predlist)

def path_linearize(path, quotefunc=urlquote):
    def elem_linearize(elem):
        linear = predlist_linearize(elem[0], quotefunc)
        if elem[1]:
            linear += '(%s)' % predlist_linearize(elem[1], quotefunc)
            if elem[2]:
                linear += ','.join(quotefunc(elem[2]))
        return linear
    return '/' + '/'.join([ elem_linearize(elem) for elem in path ])

def reduce_name_pred(x, y):
    if x.tag == 'name' and x.op == '=' and len(x.vals) > 0:
        return x.vals[0]
    elif y.tag == 'name' and y.op == '=' and len(y.vals) > 0:
        return y.vals[0]
    else:
        return None
            
def make_filter(allowed):
    allchars = string.maketrans('', '')
    delchars = ''.join([c for c in allchars if c not in allowed])
    return lambda s, a=allchars, d=delchars: (str(s)).translate(a, d)

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
    def __init__(self, ast, status, data='', headers={}, desc='%s'):
        self.detail = urlquote(desc % data)
        #web.debug(self.detail, desc, data)
        logger.info('%s%s req=%s -- %s' % (web.ctx.ip, ast and ast.authn.role and ' user=%s' % urllib.quote(ast.authn.role) or '',
                                        ast and ast.request_guid or '', desc % data))
        data = render.Error(status, desc, data)
        m = re.match('.*MSIE.*',
                     web.ctx.env.get('HTTP_USER_AGENT', 'unknown'))
        if m:
            status = '200 OK'
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class NotFound (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data='', headers={}):
        status = '404 Not Found'
        desc = 'The requested %s could not be found.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class Forbidden (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data='', headers={}):
        status = '403 Forbidden'
        desc = 'The requested %s is forbidden.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class Unauthorized (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data='', headers={}):
        status = '401 Unauthorized'
        desc = 'The requested %s requires authorization.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class BadRequest (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data='', headers={}):
        status = '400 Bad Request'
        desc = 'The request is malformed. %s'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class Conflict (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data='', headers={}):
        status = '409 Conflict'
        desc = 'The request conflicts with the state of the server. %s'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class IntegrityError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a integrity error: %s.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

class RuntimeError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, ast, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a runtime error: %s.'
        WebException.__init__(self, ast, status, headers=headers, data=data, desc=desc)

# BUG: use locking to avoid assumption that global interpreter lock protects us?
configDataCache = dict()

class Application:
    "common parent class of all service handler classes to use db etc."
    __slots__ = [ 'dbnstr', 'dbstr', 'db', 'home', 'store_path', 'chunkbytes', 'render', 'help', 'jira', 'remap', 'webauthnexpiremins' ]

    def select_config(self, pred=None, params_and_defaults=None, fake_missing=True):
        
        if pred == None:
            pred = web.Storage(tag='config', op='=', vals=['tagfiler'])

        if params_and_defaults == None:
            params_and_defaults = [ ('applet custom properties', []),
                                    ('applet test properties', []),
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
                                    ('file list tags', []),
                                    ('file list tags write', []),
                                    ('file write users', []),
                                    ('help', None),
                                    ('home', 'https://%s' % self.hostname),
                                    ('log path', '/var/www/%s-logs' % self.daemonuser),
                                    ('logo', ''),
                                    ('policy remappings', []),
                                    ('store path', '/var/www/%s-data' % self.daemonuser),
                                    ('subtitle', ''),
                                    ('tag list tags', []),
                                    ('tagdef write users', []),
                                    ('template path', '%s/tagfiler/templates' % distutils.sysconfig.get_python_lib()),
                                    ('webauthn home', None),
                                    ('webauthn require', 'False') ]

        results = self.select_files_by_predlist(subjpreds=[pred],
                                                listtags=[ "_cfg_%s" % key for key, default in params_and_defaults] + [ pred.tag, 'subject last tagged'],
                                                listas=dict([ ("_cfg_%s" % key, key) for key, default in params_and_defaults]))
        if len(results) == 1:
            config = results[0]
            #web.debug(config)
        elif not fake_missing:
            return None
        else:
            config = web.Storage(params_and_defaults)

        for key, default in params_and_defaults:
            if config[key] == None or config[key] == []:
                config[key] = default

        return config

    def select_view_all(self):
        return self.select_files_by_predlist(subjpreds=[ web.Storage(tag='view', op=None, vals=[]) ],
                                             listtags=[ 'view' ] + [ "_cfg_%s" % key for key in ['file list tags', 'file list tags write', 'tag list tags'] ],
                                             listas=dict([ ("_cfg_%s" % key, key) for key in ['file list tags', 'file list tags write', 'tag list tags'] ]))

    def select_view(self, viewname=None, default='default'):
        if viewname == None:
            viewname = default
        if viewname == None:
            return None

        view = view_cache.select(self.db, lambda : self.select_view_all(), self.authn.role, viewname)
        if view == None:
            return self.select_view(default, None)
        else:
            return view
        
    ops = [ ('', 'Tagged'),
            (':not:', 'Not tagged'),
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
                             (':not:', []),
                             ('=', ['empty']),
                             ('!=', ['empty']),
                             (':lt:', ['empty']),
                             (':leq:', ['empty']),
                             (':gt:', ['empty']),
                             (':geq:', ['empty']),
                             (':like:', ['empty', 'int8', 'timestamptz']),
                             (':simto:', ['empty', 'int8', 'timestamptz']),
                             (':regexp:', ['empty', 'int8', 'timestamptz']),
                             (':!regexp:', ['empty', 'int8', 'timestamptz']),
                             (':ciregexp:', ['empty', 'int8', 'timestamptz']),
                             (':!ciregexp:', ['empty', 'int8', 'timestamptz']) ])

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
    
    # static representation of important tagdefs
    static_tagdefs = []
    # -- the system tagdefs needed by the select_files_by_predlist call we make below and by Subject.populate_subject
    for prototype in [ ('config', 'text', False, 'subject', True),
                       ('id', 'int8', False, 'system', True),
                       ('tagdef', 'text', False, 'system', True),
                       ('tagdef type', 'type', False, 'system', False),
                       ('tagdef multivalue', 'empty', False, 'system', False),
                       ('tagdef active', 'empty', False, 'system', False),
                       ('tagdef readpolicy', 'tagpolicy', False, 'system', False),
                       ('tagdef writepolicy', 'tagpolicy', False, 'system', False),
                       ('tagdef unique', 'empty', False, 'system', False),
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
                       ('tag last modified', 'timestamptz', False, 'system', False),
                       ('name', 'text', False, 'system', False),
                       ('version', 'int8', False, 'system', False),
                       ('latest with name', 'text', False, 'system', True),
                       ('_cfg_applet custom properties', 'text', True, 'subject', False),
                       ('_cfg_applet tags', 'tagname', True, 'subject', False),
                       ('_cfg_applet tags require', 'tagname', True, 'subject', False),
                       ('_cfg_applet test log', 'text', False, 'subject', False),
                       ('_cfg_applet test properties', 'text', True, 'subject', False),
                       ('_cfg_bugs', 'text', False, 'subject', False),
                       ('_cfg_chunk bytes', 'text', False, 'subject', False),
                       ('_cfg_client chunk bytes', 'int8', False, 'subject', False),
                       ('_cfg_client socket timeout', 'int8', False, 'subject', False),
                       ('_cfg_client connections', 'int8', False, 'subject', False),
                       ('_cfg_client download chunks', 'empty', False, 'subject', False),
                       ('_cfg_client socket buffer size', 'int8', False, 'subject', False),
                       ('_cfg_client retry count', 'int8', False, 'subject', False),
                       ('_cfg_client upload chunks', 'empty', False, 'subject', False),
                       ('_cfg_contact', 'text', False, 'subject', False),
                       ('_cfg_file list tags', 'tagname', True, 'subject', False),
                       ('_cfg_file list tags write', 'tagname', True, 'subject', False),
                       ('_cfg_file write users', 'rolepat', True, 'subject', False),
                       ('_cfg_help', 'text', False, 'subject', False),
                       ('_cfg_home', 'text', False, 'subject', False),
                       ('_cfg_log path', 'text', False, 'subject', False),
                       ('_cfg_logo', 'text', False, 'subject', False),
                       ('_cfg_policy remappings', 'text', True, 'subject', False),
                       ('_cfg_store path', 'text', False, 'subject', False),
                       ('_cfg_subtitle', 'text', False, 'subject', False),
                       ('_cfg_tag list tags', 'tagname', True, 'subject', False),
                       ('_cfg_tagdef write users', 'rolepat', True, 'subject', False),
                       ('_cfg_template path', 'text', False, 'subject', False),
                       ('_cfg_webauthn home', 'text', False, 'subject', False),
                       ('_cfg_webauthn require', 'empty', False, 'subject', False) ]:
        deftagname, typestr, multivalue, writepolicy, unique = prototype
        static_tagdefs.append(web.Storage(tagname=deftagname,
                                          owner=None,
                                          typestr=typestr,
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

    def __init__(self, parser=None):
        "store common configuration data for all service classes"
        global render
        global db_cache

        def long2str(x):
            s = ''
            

        self.request_guid = base64.b64encode(  struct.pack('Q', random.getrandbits(64)) )

        self.url_parse_func = parser

        self.skip_preDispatch = False

        self.version = None
        self.subjpreds = []
        self.globals = dict()

        # this ordered list can be pruned to optimize transactions
        self.needed_db_globals = [ 'tagdefsdict', 'roleinfo', 'typeinfo', 'typesdict' ]

        myAppName = os.path.basename(web.ctx.env['SCRIPT_NAME'])

        def getParamEnv(suffix, default=None):
            return web.ctx.env.get('%s.%s' % (myAppName, suffix), default)

        try:
            p = subprocess.Popen(['/usr/bin/whoami'], stdout=subprocess.PIPE)
            line = p.stdout.readline()
            self.daemonuser = line.strip()
        except:
            self.daemonuser = 'tagfiler'

        self.hostname = socket.gethostname()

        self.logmsgs = []
        self.middispatchtime = None

        self.dbnstr = getParamEnv('dbnstr', 'postgres')
        self.dbstr = getParamEnv('dbstr', '')
        self.db = web.database(dbn=self.dbnstr, db=self.dbstr)


        # BEGIN: get runtime parameters from database
        self.globals['tagdefsdict'] = Application.static_tagdefs # need these for select_config() below

        # set default anonymous authn info
        self.set_authn(webauthn.providers.AuthnInfo(None, set([]), None, None, False, None))

        def fill_config():
            config = self.select_config()
            config['policy remappings'] = buildPolicyRules(config['policy remappings'])
            return [ config ]

        # get full config
        self.config = config_cache.select(self.db, fill_config, self.authn.role, 'tagfiler')
        del self.globals['tagdefsdict'] # clear this so it will be rebuilt properly during transaction
        
        #self.config = self.select_config()
        #self.config['policy remappings'] = buildPolicyRules(self.config['policy remappings'])
        
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
        self.globals['browsersImmutableTags'] = [ 'check point offset', 'key', 'sha256sum' ]
        
        # END: get runtime parameters from database

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

    def validateSubjectQuery(self, query, tagdef=None, subject=None):
        if type(query) in [ int, long ]:
            return
        if type(query) in [ type('string'), unicode ]:
            ast = self.url_parse_func(query)
            if hasattr(ast, 'is_subquery') and ast.is_subquery:
                # this holds a subquery expression to evaluate
                return [ subject.id for subject in self.select_files_by_predlist_path(path=ast.path) ]
            elif type(ast) in [ int, long ]:
                # this is a bare subject identifier
                return ast
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
            results = typedef_cache.select(self.db, lambda: self.get_type(), self.authn.role, typename)
            if len(results) == 0:
                raise Conflict(self, 'The type "%s" is not defined!' % typename)
            type = results[0]
            dbtype = type['typedef dbtype']
            try:
                key = self.downcast_value(dbtype, key)
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

    def logfmt_old(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        parts = []
        if dataset:
            parts.append('dataset "%s"' % dataset)
        if tag:
            parts.append('tag "%s"' % tag)
        if value:
            parts.append('value "%s"' % value)
        if mode:
            parts.append('mode "%s"' % mode)

        return ('%s ' % action) + ', '.join(parts)

    def lograw(self, msg):
        logger.info(msg)

    def logfmt(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        return '%s%s req=%s -- %s' % (web.ctx.ip, self.authn.role and ' user=%s' % urlquote(self.authn.role) or '', 
                                      self.request_guid, self.logfmt_old(action, dataset, tag, mode, user, value))

    def log(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        self.lograw(self.logfmt(action, dataset, tag, mode, user, value))

    def txlog(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        self.logmsgs.append(self.logfmt(action, dataset, tag, mode, user, value))

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
 
        return "".join([unicode(r) for r in 
                        [self.render.Top()] 
                        + renderlist
                        + [self.render.Bottom()]])

    def preDispatchFake(self, uri, app):
        self.db = app.db
        self.set_authn(app.authn)
        # we need to re-do this after having proper authn info
        #self.globals['tagdefsdict'] = dict([ (tagdef.tagname, tagdef) for tagdef in tagdef_cache.select(self.db, lambda: self.select_tagdef()) ])
        #self.globals['tagdefsdict'] = dict ([ (tagdef.tagname, tagdef) for tagdef in self.select_tagdef() ])

    def preDispatchCore(self, uri, setcookie=True):
        self.request_uri = uri
        if self.globals['webauthnhome']:
            if not self.db:
                self.db = web.database(dbn=self.dbnstr, db=self.dbstr)
            self.set_authn(webauthn.session.test_and_update_session(self.db,
                                                                    referer=self.config.home + uri,
                                                                    setcookie=setcookie))
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

        # we need to re-do this after having proper authn info
        #self.globals['tagdefsdict'] = dict([ (tagdef.tagname, tagdef) for tagdef in tagdef_cache.select(self.db, lambda: self.select_tagdef()) ])
        #self.globals['tagdefsdict'] = dict ([ (tagdef.tagname, tagdef) for tagdef in self.select_tagdef() ])

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
        return
        #now = datetime.datetime.now()
        #if self.middispatchtime == None or (now - self.middispatchtime).seconds > 30:
        #    self.preDispatchCore(web.ctx.homepath, setcookie=False)

    def setNoCache(self):
        now = datetime.datetime.now(pytz.timezone('UTC'))
        now_rfc1123 = now.strftime(Application.rfc1123)
        web.header('Cache-control', 'no-cache')
        web.header('Expires', now_rfc1123)

    def logException(self, context=None):
        if context == None:
            context = 'unspecified'
        et, ev, tb = sys.exc_info()
        web.debug('exception "%s"' % context,
                  traceback.format_exception(et, ev, tb))

    def dbtransact(self, body, postCommit):
        """re-usable transaction pattern

           using caller-provided thunks under boilerplate
           commit/rollback/retry logic
        """
        if not self.db:
            self.db = web.database(dbn=self.dbnstr, db=self.dbstr)

        try:
            count = 0
            limit = 8
            error = None
            while True:
                try:
                    t = self.db.transaction()
                    
                    try:
                        self.logmsgs = []
                        count = count + 1
                        self.subject = None
                        self.datapred = None
                        self.dataname = None
                        self.dataid = None

                        # build up globals useful to almost all classes, to avoid redundant coding
                        # this is fragile to make things fast and simple
                        db_globals_dict = dict(roleinfo=lambda : self.buildroleinfo(),
                                               typeinfo=lambda : [ x for x in typedef_cache.select(self.db, lambda: self.get_type(), self.authn.role)],
                                               typesdict=lambda : dict([ (type['typedef'], type) for type in self.globals['typeinfo'] ]),
                                               tagdefsdict=lambda : dict([ (tagdef.tagname, tagdef) for tagdef in tagdef_cache.select(self.db, lambda: self.select_tagdef(), self.authn.role) ]) )
                        for key in self.needed_db_globals:
                            if not self.globals.has_key(key):
                                self.globals[key] = db_globals_dict[key]()

                        def tagOptions(tagname, values=[]):
                            tagdef = self.globals['tagdefsdict'][tagname]
                            tagnames = self.globals['tagdefsdict'].keys()
                            type = self.globals['typesdict'][tagdef.typestr]
                            typevals = type['typedef values']
                            tagref = type['typedef tagref']
                            roleinfo = self.globals['roleinfo']

                            if typevals:
                                options = [ ( typeval[0], '%s (%s)' % typeval ) for typeval in typevals.items() ]
                            elif tagdef.typestr in [ 'role', 'rolepat' ]:
                                if roleinfo != None:
                                    if tagdef.typestr == 'rolepat':
                                        options = [ (role, role) for role in set(roleinfo).union(set(['*'])).difference(set(values)) ]
                                    else:
                                        options = [ (role, role) for role in set(roleinfo).difference(set(values)) ]
                                else:
                                    options = None
                            elif tagref:
                                if tagref in tagnames:
                                    options = [ (value, value) for value in
                                                set([ res.value for res in self.db.query('SELECT DISTINCT value FROM %s' % self.wraptag(tagref))])
                                                .difference(set(values)) ]
                                else:
                                    options = None
                            elif tagdef.typestr == 'tagname' and tagnames:
                                options = [ (tag, tag) for tag in set(tagnames).difference(set(values)) ]
                            else:
                                options = None
                            return options

                        self.globals['tagOptions'] = tagOptions

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

                        bodyval = body()
                        t.commit()
                        break
                        # syntax "Type as var" not supported by Python 2.4
                    except (psycopg2.InterfaceError), te:
                        # pass this to outer handler

                        raise te
                    except (web.SeeOther), te:
                        t.commit()
                        raise te
                    except (NotFound, BadRequest, Unauthorized, Forbidden, Conflict), te:
                        t.rollback()
                        raise te
                    except (psycopg2.DataError, psycopg2.ProgrammingError), te:
                        t.rollback()
                        raise BadRequest(self, data='Logical error: %s.' % str(te))
                    except TypeError, te:
                        t.rollback()
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
                    self.db = web.database(db=self.dbstr, dbn=self.dbnstr)

                # exponential backoff...
                # count=1 is roughly 0.1 microsecond
                # count=9 is roughly 10 seconds
                # randomly jittered from 75-125% of exponential delay
                delay =  random.uniform(0.75, 1.25) * math.pow(10.0, count) * 0.00000001
                web.debug('transaction retry: delaying %f on "%s"' % (delay, error))
                time.sleep(delay)

        finally:
            pass
                    
        for msg in self.logmsgs:
            logger.info(msg)
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

    def buildroleinfo(self):
        if self.authn.roleProvider:
            try:
                roleinfo = [ role for role in self.authn.roleProvider.listRoles(self.db) ]
                return roleinfo
            except NotImplemented, AttributeError:
                return None

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
                + [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique and tagdef.tagname] :
            keyv = subject.get(dtype, None)
            if keyv:
                return dtype

    def subject2identifiers(self, subject, showversions=True):
        dtype = self.classify_subject(subject)
        # [ 'tagdef', 'typedef', 'config', 'view' ]
        if dtype in  set([ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique ]).difference(set(['file'])):
            keyv = subject.get(dtype, None)
            if self.globals['tagdefsdict'][dtype].multivalue:
                keyv = keyv[0]
            datapred = '%s=%s' % (urlquote(dtype), urlquote(keyv))
            dataid = datapred
            dataname = '%s=%s' % (dtype, keyv)
        else:
            name = subject.get('name', None)
            version = subject.get('version', None)
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
                    key = self.downcast_value(dbtype, key)
                    vals.append( (key, desc) )
                res['typedef values'] = dict(vals)
            return res
        if typename != None:
            subjpreds = [ web.Storage(tag='typedef', op='=', vals=[typename]) ]
        else:
            subjpreds = [ web.Storage(tag='typedef', op=None, vals=[]) ]
        listtags = [ 'typedef', 'typedef description', 'typedef dbtype', 'typedef values', 'typedef tagref' ]
        return [ valexpand(res) for res in self.select_files_by_predlist(subjpreds=subjpreds, listtags=listtags) ]

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
        return self.db.query(query, vars)

    def select_dataset_size(self, key, membertag='vcontains'):
        # return statistics aout the children of the dataset as referenced by its membertag
        query, values = self.build_files_by_predlist_path([ ([web.Storage(tag='key', op='=', vals=[key])], [web.Storage(tag=membertag,op=None,vals=[])], []),
                                                            ([], [ web.Storage(tag=tag,op=None,vals=[]) for tag in 'name', 'bytes' ], []) ])
        query = 'SELECT SUM(bytes) AS size, COUNT(*) AS count FROM (%s) AS q' % query
        return self.db.query(query, values)

    def insert_file(self, name, version, file=None):
        newid = self.db.query("INSERT INTO resources DEFAULT VALUES RETURNING subject")[0].subject
        subject = web.Storage(id=newid)

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
        self.db.query('UPDATE "_latest with name" SET subject = $id WHERE value = $name', vars=vars)

    def delete_file(self, subject):
        wheres = []

        if subject.name and subject.version:
            versions = [ file for file in self.select_file_versions(subject.name) ]
            versions.sort(key=lambda res: res.version, reverse=True)

            latest = versions[0]
        
            if subject.version == latest.version and len(versions) > 1:
                # we're deleting the latest version and there are previous versions
                self.update_latestfile_version(subject.name, versions[1].id)

        results = self.db.query('SELECT * FROM subjecttags WHERE subject = $subject', vars=dict(subject=subject.id))
        for result in results:
            self.set_tag_lastmodified(None, self.globals['tagdefsdict'][result.tagname])
                
        query = 'DELETE FROM resources WHERE subject = $id'
        self.db.query(query, vars=dict(id=subject.id))

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
            ordertags = [ order ]
        else:
            ordertags = []

        def add_authz(tagdef):
            for mode in ['read', 'write']:
                tagdef['%sok' % mode] = self.test_tag_authz(mode, None, tagdef)

            return tagdef
            
        if tagname:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op='=', vals=[tagname]) ]
        else:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op=None, vals=[]) ]

        results = [ add_authz(tagdef) for tagdef in self.select_files_by_predlist(subjpreds, listtags, ordertags, listas=Application.tagdef_listas, tagdefs=Application.static_tagdefs, enforce_read_authz=enforce_read_authz) ]
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
            tags.append( ('tagdef multivalue', None) )
        if self.is_unique:
            tags.append( ('tagdef unique', None) )

        for tag, value in tags:
            self.set_tag(subject, self.globals['tagdefsdict'][tag], value)

        tagdef = web.Storage([ (Application.tagdef_listas.get(key, key), value) for key, value in tags ])
        tagdef.id = newid
        if owner == None:
            tagdef.owner = None
        tagdef.multivalue = self.multivalue

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
            tabledef += ' NOT NULL'

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
        self.db.query(tabledef)
        if indexdef:
            self.db.query(indexdef)

    def delete_tagdef(self, tagdef):
        self.undeploy_tagdef(tagdef)
        tagdef.name = None
        tagdef.version = None
        self.delete_file( tagdef )

    def undeploy_tagdef(self, tagdef):
        self.db.query('DROP TABLE %s' % (self.wraptag(tagdef.tagname)))

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
        return self.db.query(query, vars=vars)

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
        return self.db.query(query, vars=vars)

    def set_tag_lastmodified(self, subject, tagdef):
        if tagdef.tagname in [ 'tag last modified', 'tag last modified txid', 'subject last tagged', 'subject last tagged txid' ]:
            # don't recursively track tags we generate internally
            return

        def insert_or_update(table, vars):
            self.db.query('LOCK TABLE %s IN EXCLUSIVE MODE' % table)
            results = self.db.query('SELECT value FROM %s WHERE subject = $subject'  % table, vars=vars)

            if len(results) > 0:
                value = results[0].value
                if value < vars['now']:
                    self.db.query('UPDATE %s SET value = $now WHERE subject = $subject' % table, vars=vars)
                    #web.debug('set %s from %s to %s' % (table, value, vars['now']))
                elif value == vars['now']:
                    pass
                else:
                    pass
                    #web.debug('refusing to set %s from %s to %s' % (table, value, vars['now']))
            else:
                self.db.query('INSERT INTO %s (subject, value) VALUES ($subject, $now)' % table, vars=vars)
                #web.debug('set %s to %s' % (table, vars['now']))

        now = datetime.datetime.now(pytz.timezone('UTC'))
        txid = self.db.query('SELECT txid_current() AS txid')[0].txid

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
        deleted = self.db.query(query, vars=vars)
        if len(deleted) > 0:
            self.set_tag_lastmodified(subject, tagdef)

            results = self.select_tag_noauthn(subject, tagdef)
            if len(results) == 0:
                query = 'DELETE FROM subjecttags AS tag WHERE subject = $id AND tagname = $tagname'
                self.db.query(query, vars=vars)

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

    def downcast_value(self, dbtype, value):
        if dbtype == 'int8':
            value = int(value)
        elif dbtype == 'float8':
            value = float(value)
        elif dbtype in [ 'date', 'timestamptz' ]:
            if value == 'now':
                value = datetime.datetime.now(pytz.timezone('UTC'))
            elif type(value) == str:
                value = dateutil.parser.parse(value)
        else:
            pass
        return value

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

            try:
                if value:
                    value = self.downcast_value(dbtype, value)
            except:
                raise BadRequest(self, data='The value "%s" cannot be converted to stored type "%s".' % (value, dbtype))

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

                results = self.db.query(query, vars=vars)

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

        self.db.query(query, vars=vars)

        # update in-memory representation too for caller's sake
        if tagdef.multivalue:
            subject[tagdef.tagname] = [ res.value for res in self.select_tag_noauthn(subject, tagdef) ]
        elif tagdef.typestr != 'empty':
            subject[tagdef.tagname] = self.select_tag_noauthn(subject, tagdef)[0].value
        else:
            subject[tagdef.tagname] = True
        
        results = self.select_filetags_noauthn(subject, tagdef.tagname)
        if len(results) == 0:
            results = self.db.query("INSERT INTO subjecttags (subject, tagname) VALUES ($subject, $tagname)", vars=vars)
        else:
            # may already be reverse-indexed in multivalue case
            pass

        self.set_tag_lastmodified(subject, tagdef)
        

    def select_next_transmit_number(self):
        query = "SELECT NEXTVAL ('transmitnumber')"
        vars = dict()
        # now, as we can set manually dataset names, make sure the new generated name is unique
        while True:
            result = self.db.query(query)
            name = str(result[0].nextval).rjust(9, '0')
            vars['value'] = name
            res = self.db.query('SELECT * FROM "_name" WHERE value = $value', vars)
            if len(res) == 0:
                return name

    def select_next_key_number(self):
        query = "SELECT NEXTVAL ('keygenerator')"
        vars = dict()
        # now, as we can set manually dataset names, make sure the new generated name is unique
        while True:
            result = self.db.query(query)
            value = str(result[0].nextval).rjust(9, '0')
            vars['value'] = value
            res = self.db.query('SELECT * FROM "_key" WHERE value = $value', vars)
            if len(res) == 0:
                return value

    def build_select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, version=None, qd=0, versions='latest', listas=None, tagdefs=None, enforce_read_authz=True, limit=None, assume_roles=False, listpreds=None, vprefix=''):

        #web.debug(subjpreds, listtags, ordertags, listas)

        if listas == None:
            listas = dict()

        def dbquote(s):
            return s.replace("'", "''")
        
        if subjpreds == None:
            subjpreds = self.subjpreds

        if listpreds == None:
            if listtags == None:
                listtags = [ x for x in self.globals['filelisttags'] ]
            else:
                listtags = [ x for x in listtags ]

            listpreds = [ web.Storage(tag=tag, op=None, vals=[]) for tag in listtags ]
        else:
            listpreds = [ x for x in listpreds ]

        if ordertags:
            listpreds = listpreds + [ web.Storage(tag=tag, op=None, vals=[]) for tag in ordertags ]

        for tag in [ 'id', 'owner' ]:
            listpreds.append( web.Storage(tag=tag, op=None, vals=[]) )

        listpredsdict = dict()
        for pred in listpreds:
            preds = listpredsdict.get(pred.tag, [])
            listpredsdict[pred.tag] = preds + [ pred ]

        roles = [ r for r in self.authn.roles ]
        roles.append('*')

        if tagdefs == None:
            tagdefs = self.globals['tagdefsdict']

        tags_needed = set([ pred.tag for pred in subjpreds ])
        tags_needed = tags_needed.union(set(listpredsdict.iterkeys()))
        tagdefs_needed = []
        for tagname in tags_needed:
            try:
                tagdefs_needed.append(tagdefs[tagname])
            except KeyError:
                #web.debug(tagname)
                raise BadRequest(self, data='The tag "%s" is not defined on this server.' % tagname)

        innertables = []  # (table, alias)
        innertables_special = []
        outer_prepend_owner = True
        outertables = []
        outertables_special = []
        selects = ['subject AS subject', '_owner.value AS owner']
        wheres = []
        values = dict()

        need_subjectowner_test = False

        with_prefix = 'WITH rawroles (role) AS ( VALUES %s )' % ','.join(["('%s')" % dbquote(role) for role in roles] + [ '( NULL )'])
        with_prefix += ', roles (role) AS ( SELECT role FROM rawroles WHERE role IS NOT NULL ) '

        for p in range(0, len(subjpreds)):
            pred = subjpreds[p]
            tag = pred.tag
            op = pred.op
            vals = pred.vals
            tagdef = tagdefs[tag]

            if op == ':not:':
                # not matches if tag column is null
                if tag == 'id':
                    raise Conflict(self, 'The "id" tag is bound for all catalog entries and is non-sensical to use with the :not: operator.')
                outertables.append((self.wraptag(tag), 't%s%s' % (vprefix, p) ))
                if tagdef.readok == False and enforce_read_authz:
                    # this tag cannot be read so act like it is absent
                    wheres.append('True')
                elif tagdef.readpolicy == 'subjectowner' and enforce_read_authz:
                    # this tag rule is more restrictive than file or static checks already done
                    # act like it is NULL if user isn't allowed to read this tag
                    outertables_special.append( 'roles AS ownerrole_%d ON (_owner.value = ownerrole_%d.role)' % (p, p) )
                    wheres.append('t%s%s.subject IS NULL OR (ownerrole_%d.role IS NULL)' % (vprefix, p, p))
                else:
                    # covers all cases where tag is more or equally permissive to file or static checks already done
                    # e.g. read policy in [ 'subject', 'tagandsubject', 'tag', 'tagorsubject', 'anonymous' ]
                    wheres.append('t%s%s.subject IS NULL' % (vprefix, p))
            elif op == 'IN':
                # special internal operation to restrict by sub-query, doesn't need to be sanity checked
                if tag == 'id':
                    wheres.append('subject IN (%s)' % (vals))
                else:
                    innertables.append((self.wraptag(tag), 't%s%s' % (vprefix, p)))
                    wheres.append('t%s%s.value IN (%s)' % (vprefix, p, vals))
            else:
                # all others match if and only if tag column is not null and we have read access
                # ...and any value constraints are met
                if tagdef.readok == False and enforce_read_authz:
                    # this predicate is conjunctive with access denial
                    wheres.append('False')
                else:
                    if tagdef.readpolicy == 'subjectowner' and enforce_read_authz:
                        # this predicate is conjunctive with more restrictive access check, which we only need to add once
                        need_subjectowner_test = True
                    else:
                        # covers all cases where tag is more or equally permissive to file or static checks already done
                        # e.g. read policy in [ 'subject', 'tagandsubject', 'tag', 'tagorsubject', 'anonymous' ]
                        pass
                                    
                    if tag != 'id':
                        innertables.append((self.wraptag(tag), 't%s%s' % (vprefix, p)))

                    if op and vals and len(vals) > 0:
                        valpreds = []
                        for v in range(0, len(vals)):
                            if hasattr(vals[v], 'is_subquery'):
                                typedef = self.globals['typesdict'][tagdef.typestr]
                                if op != '=':
                                    raise BadRequest(self, 'Operator "%s" not allowed with subquery for subject predicate values.' % op)
                                
                                sq_path = [ x for x in vals[v].path ]
                                sq_subjpreds, sq_listpreds, sq_ordertags = sq_path[-1]
                                sq_listpreds = [ x for x in sq_listpreds ]
                                
                                if typedef['typedef tagref']:
                                    # subquery needs to generate results by tagref tagname
                                    sq_listpreds.append( web.Storage(tag=typedef['typedef tagref'], op=None, vals=[]) )
                                    sq_project = typedef['typedef tagref']
                                elif tagdef.tagname == 'id':
                                    # subquery just needs to generate results w/ ID
                                    sq_project = 'id'
                                else:
                                    raise BadRequest(self, 'Subquery predicate not supported for tag "%s".' % tagdef.tagname)
                                
                                sq_path[-1] = ( sq_subjpreds, sq_listpreds, sq_ordertags )
                                q, qvs = self.build_files_by_predlist_path(path=sq_path, versions=versions, assume_roles=True, vprefix="%sv%s_%s_%d__" % (vprefix, p, v, qd))
                                sq = "SELECT DISTINCT \"%s\" FROM (%s) AS sq_%s%s_%s_%d" % (sq_project, q, vprefix, p, v, qd)
                                values.update(qvs)
                                valpreds.append("t%s%s.value IN (%s)" % (vprefix, p, sq))
                            else:
                                if tag != 'id':
                                    valpreds.append("t%s%s.value %s $val%s%s_%s_%d" % (vprefix, p, Application.opsDB[op], vprefix, p, v, qd))
                                else:
                                    valpreds.append("subject %s $val%s%s_%s_%d" % (Application.opsDB[op], vprefix, p, v, qd))
                                values["val%s%s_%s_%d" % (vprefix, p, v, qd)] = vals[v]
                        wheres.append(" OR ".join(valpreds))
                    

        outertables_special.append( 'roles AS readerrole ON ("_read users".value = readerrole.role)' )
        if enforce_read_authz:
            if need_subjectowner_test:
                # at least one predicate test requires subjectowner-based read access rights
                outer_prepend_owner = False # need to suppress normal placement of owner and get it before we use it
                innertables.append( ( '_owner', None ) )
                innertables_special.append( 'roles AS ownerrole ON (_owner.value = ownerrole.role)' )
            else:
                outertables_special.append( 'roles AS ownerrole ON (_owner.value = ownerrole.role)' )

            # all results are filtered by file read access rights
            wheres.append('ownerrole.role IS NOT NULL OR readerrole.role IS NOT NULL')
            # compute read access rights for later consumption
            selects.append('bool_or(True) AS readok')
        else:
            # compute read access rights for later consumption
            outertables_special.append( 'roles AS ownerrole ON (_owner.value = ownerrole.role)' )
            selects.append('bool_or(ownerrole.role IS NOT NULL OR readerrole.role IS NOT NULL) AS readok')

        if outer_prepend_owner:
            outertables = [ ( '_owner', None ) ] + outertables

        # compute file write access rights for later consumption
        outertables_special.append( 'roles AS writerrole ON ("_write users".value = writerrole.role)' )
        selects.append('bool_or(ownerrole.role IS NOT NULL OR writerrole.role IS NOT NULL) AS writeok')

        # retain summary of ownership for later consumption by read-enforced tag projection
        selects.append('bool_or(ownerrole.role IS NOT NULL) AS is_owner')

        if id:
            # special single-entry lookup
            values['id_%s%d' % (vprefix, qd)] = id
            wheres.append("subject = $id_%s%d" % (vprefix, qd))

        # constrain to latest named files ONLY
        if versions == 'latest':
            outertables.append(('"_latest with name"', None))
            outertables.append(('_name', None))
            wheres.append('"_name".value IS NULL OR "_latest with name".value IS NOT NULL')

        outertables = outertables \
                      + [('"_read users"', None),
                         ('"_write users"', None)]

        # idempotent insertion of (table, alias)
        joinset = set()
        innertables2 = []
        outertables2 = []

        if len(innertables) == 0:
            innertables.append( ('resources', None) ) # make sure we have at least one entry for 'subject'

        for tablepair in innertables:
            if tablepair not in joinset:
                innertables2.append(tablepair)
                joinset.add(tablepair)

        for tablepair in outertables:
            if tablepair not in joinset:
                outertables2.append(tablepair)
                joinset.add(tablepair)

        def rewrite_tablepair(tablepair, suffix=''):
            table, alias = tablepair
            if alias:
                table += ' AS %s' % alias
            return table + suffix

        innertables2 = [ rewrite_tablepair(innertables2[0]) ] \
                       + [ rewrite_tablepair(table, ' USING (subject)') for table in innertables2[1:] ] \
                       + innertables_special
        outertables2 = [ rewrite_tablepair(table, ' USING (subject)') for table in outertables2 ] \
                       + outertables_special

        # this query produces a set of (subject, owner, readok, writeok, is_owner) rows that match the query result set
        subject_query = 'SELECT %s' % ','.join(selects) \
                        + ' FROM %s' % ' LEFT OUTER JOIN '.join([' JOIN '.join(innertables2)] + outertables2 ) \
                        + ' WHERE %s' % ' AND '.join([ '(%s)' % where for where in wheres ]) \
                        + ' GROUP BY subject, owner'

        # now build the outer query that attaches listtags metadata to results
        core_tags = dict(owner='subjects.owner',
                         id='subjects.subject')
        
        selects = [ 'subjects.readok AS readok', 'subjects.writeok AS writeok', 'subjects.is_owner AS is_owner' ]
        innertables = [('(%s)' % subject_query, 'subjects')]
        outertables = []
        groupbys = [ 'subjects.readok', 'subjects.writeok', 'subjects.is_owner' ]

        def make_listwhere(t, vref, preds, tagdef):
            listwheres = []
            for p in range(0, len(preds)):
                pred = preds[p]
                if pred.op == ':not:':
                    # non-sensical listpred cannot ever select a triple
                    listwheres.append( 'False' )
                elif pred.op == 'IN':
                    # don't support this yet (or ever?)
                    raise ValueError
                elif pred.op and pred.vals:
                    if tagdef.typestr == 'empty':
                        raise BadRequest(self, 'Inappropriate operator "%s" for tag "%s".' % (pred.op, pred.tag))
                    valpreds = []
                    for v in range(0, len(pred.vals)):
                        if hasattr(pred.vals[v], 'is_subquery'):
                            typedef = self.globals['typesdict'][tagdef.typestr]
                            if pred.op not in [ '=', 'IN' ]:
                                raise BadRequest(self, 'Operator "%s" not allowed with subquery for list predicate values.' % op)
                            
                            sq_path = [ x for x in pred.vals[v].path ]
                            sq_subjpreds, sq_listpreds, sq_ordertags = sq_path[-1]
                            sq_listpreds = [ x for x in sq_listpreds ]
                            
                            if typedef['typedef tagref']:
                                # subquery needs to generate results by tagref tagname
                                sq_listpreds.append( web.Storage(tag=typedef['typedef tagref'], op=None, vals=[]) )
                                sq_project = typedef['typedef tagref']
                            elif tagdef.tagname == 'id':
                                # subquery just needs to generate results w/ ID
                                sq_project = 'id'
                            else:
                                raise BadRequest(self, 'Subquery predicate not supported for tag "%s".' % tagdef.tagname)

                            sq_path[-1] = ( sq_subjpreds, sq_listpreds, sq_ordertags )
                            q, qvs = self.build_files_by_predlist_path(path=sq_path, versions=versions, assume_roles=True, vprefix="%sp%s_%s_%d__" % (vprefix, p, v, qd))
                            sq = "SELECT DISTINCT \"%s\" FROM (%s) AS sq_%s%s_%s_%d" % (sq_project, q, vprefix, p, v, qd)
                            values.update(qvs)
                            valpreds.append("%s IN (%s)" % (vref, sq))
                        else:
                            valpreds.append( '%s %s $listval_%s%s_%d_%d_%d' % (vref, Application.opsDB[pred.op], vprefix, t, p, v, qd) )
                            values['listval_%s%s_%d_%d_%d' % (vprefix, t, p, v, qd)] = pred.vals[v]
                    listwheres.append( ' OR '.join([ '(%s)' % valpred for valpred in valpreds ]) )
                        
            return ' AND '.join([ '(%s)' % listwhere for listwhere in listwheres])
           
        # build custom projection of matching subjects
        listtags = [ t for t in listpredsdict.iterkeys() if t not in ['readok', 'writeok'] ]
        for t in range(0, len(listtags)):
            tag = listtags[t]
            tagdef = tagdefs[tag]
            preds = listpredsdict[tag]

            if tagdef.multivalue:
                listwhere = make_listwhere(t, '%s.value' % self.wraptag(tag), preds, tagdef)
                if listwhere:
                    listwhere = 'WHERE ' + listwhere

                outertables.append(('(SELECT subject, array_agg(value) AS value FROM %s %s GROUP BY subject)' % (self.wraptag(tag), listwhere), self.wraptag(tag)))
                expr = '%s.value' % self.wraptag(tag)
                groupbys.append(expr)
            else:
                if tag not in core_tags:
                    outertables.append((self.wraptag(tag), None))
                if tagdef.typestr == 'empty':
                    expr = '%s.subject' % self.wraptag(tag)
                    groupbys.append(expr)
                    expr += ' IS NOT NULL'
                    listwhere = make_listwhere(t, None, preds, tagdef)
                else:
                    expr = core_tags.get(tag, '%s.value' % self.wraptag(tag))
                    groupbys.append(expr)
                    listwhere = make_listwhere(t, expr, preds, tagdef)

                if listwhere:
                    expr = 'CASE WHEN %s THEN %s ELSE NULL END' % (listwhere, expr)

            if enforce_read_authz:
                if tagdef.readok == False:
                    expr = 'NULL'
                elif tagdef.readok:
                    # we can read this tag for any subject we can find
                    pass
                elif tagdef.readpolicy in [ 'subject', 'tagorsubject', 'tagandsubject' ]:
                    # we can read this tag for any subject we can read
                    # which is all subjects being read, when we are enforcing
                    pass
                elif tagdef.readpolicy == 'subjectowner':
                    # need to condition read on subjectowner test
                    expr = 'CASE WHEN subjects.is_owner THEN %s ELSE NULL END' % expr
                else:
                    raise RuntimeError(self, 'Unimplemented list-tags authorization scenario in query by predlist for tag "%s".', tagdef.tagname)
                
            selects.append('%s AS %s' % (expr, self.wraptag(listas.get(tag, tag), prefix='')))
                
        innertables2 = [ rewrite_tablepair(innertables[0]) ] \
                       + [ rewrite_tablepair(table, ' USING (subject)') for table in innertables[1:] ]
        outertables2 = [ rewrite_tablepair(table, ' USING (subject)') for table in outertables ]

        # this query produces a set of (subject, owner, readok, writeok, other tags...) rows that match the query result set
        value_query = 'SELECT %s' % ','.join(selects) \
                        + ' FROM %s' % ' LEFT OUTER JOIN '.join([' JOIN '.join(innertables2)] + outertables2 ) \
                        + ' GROUP BY %s' % ','.join(groupbys)

        if not assume_roles:
            value_query = with_prefix + value_query

        # set up reasonable default sort order to use as minor sort criteria after major user-supplied ordering(s)
        order_suffix = []
        for tagname in ['modified', 'name', 'config', 'view', 'tagdef', 'typedef', 'id']:
            if tagname in listpredsdict:
                orderstmt = self.wraptag(listas.get(tagname, tagname), prefix='')
                if tagname in [ 'modified' ]:
                    orderstmt += ' DESC'
                else:
                    orderstmt += ' ASC'
                orderstmt += ' NULLS LAST'
                order_suffix.append(orderstmt)

        if ordertags != None and (len(ordertags) > 0 or len(order_suffix) > 0):
            value_query += " ORDER BY " + ", ".join([self.wraptag(listas.get(tag, tag), prefix='') for tag in ordertags] + order_suffix)

        if limit:
            value_query += ' LIMIT %d' % limit

        #web.debug(value_query)
        return (value_query, values)

    def select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, version=None, versions='latest', listas=None, tagdefs=None, enforce_read_authz=True, limit=None, listpreds=None):

        query, values = self.build_select_files_by_predlist(subjpreds, listtags, ordertags, id=id, version=version, versions=versions, listas=listas, tagdefs=tagdefs, enforce_read_authz=enforce_read_authz, limit=limit, listpreds=None)

        #web.debug(len(query), query, values)
        #web.debug('%s bytes in query:' % len(query))
        #for string in query.split(','):
        #    web.debug (string)
        #web.debug(values)
        #web.debug('...end query')
        #for r in self.db.query('EXPLAIN ANALYZE %s' % query, vars=values):
        #    web.debug(r)
        return self.db.query(query, vars=values)

    def build_files_by_predlist_path(self, path=None, versions='latest', limit=None, enforce_read_authz=True, vprefix='', assume_roles=False):
        values = dict()
        tagdefs = self.globals['tagdefsdict']
        typedefs = self.globals['typesdict']
        
        def build_query_recursive(stack, qd, limit):
            subjpreds, listpreds, ordertags = stack[0]
            subjpreds = [ p for p in subjpreds ]
            if len(stack) == 1:
                # this query element is not contextualized
                q, v = self.build_select_files_by_predlist(subjpreds, ordertags, qd=qd, versions=versions, tagdefs=tagdefs, limit=limit, assume_roles=assume_roles or qd!=0, listpreds=listpreds, enforce_read_authz=enforce_read_authz, vprefix=vprefix)
                values.update(v)
                return q
            else:
                # this query element is contextualized
                cstack = stack[1:]
                csubjpreds, clistpreds, cordertags = cstack[0]
                
                if len(clistpreds) != 1:
                    raise BadRequest(self, "Path context %d has ambiguous projection with %d elements." % (len(cstack)-1, len(clistpreds)))
                projection = clistpreds[0].tag

                tagref = typedefs[tagdefs[projection].typestr]['typedef tagref']
                if tagref == None and tagdefs[projection].typestr not in [ 'text', 'id' ]:
                    raise BadRequest(self, 'Projection tag "%s" does not have a valid type to be used as a file context.' % projection)
                
                if tagref != None:
                    context_attr = tagref
                else:
                    context_attr = dict(text='name', id='id')[tagdefs[projection].typestr]
                if tagdefs[projection].multivalue:
                    projectclause = 'unnest("%s")' % projection
                else:
                    projectclause = '"%s"' % projection
                    
                cstack[0] = csubjpreds, clistpreds, None # don't bother sorting context more than necessary
                cq = build_query_recursive(cstack, qd + 1, limit=None)
                cq = "SELECT DISTINCT %s FROM (%s) AS context_%d" % (projectclause, cq, qd) # gives set of context values
                
                subjpreds.append( web.Storage(tag=context_attr, op='IN', vals=cq) )  # use special predicate IN with sub-query expression
                q, v = self.build_select_files_by_predlist(subjpreds, ordertags, qd=qd, versions=versions, tagdefs=tagdefs, limit=limit, assume_roles=assume_roles or qd!=0, listpreds=listpreds, enforce_read_authz=enforce_read_authz, vprefix=vprefix)
                values.update(v)
                return q
        
        if path == None:
            path = [ ([], [], []) ]

        # query stack is path in reverse... final result element in front, projected context behind
        stack = [ e for e in path ]
        stack.reverse()

        query = build_query_recursive(stack, qd=0, limit=limit)

        #web.debug(query, values)
        #traceInChunks(query)
        #web.debug('values', values)
        return (query, values)

    def select_files_by_predlist_path(self, path=None, versions='latest', limit=None, enforce_read_authz=True):
        query, values = self.build_files_by_predlist_path(path, versions, limit=limit, enforce_read_authz=enforce_read_authz)
        return self.db.query(query, values)

    
    def prepare_path_query(self, path, list_priority=['path', 'list', 'view', 'default'], list_prefix=None, extra_tags=[]):
        """Prepare (path, listtags, writetags, limit, versions) from input path, web environment, and input policies.

           list_priority  -- chooses first successful source of listtags

                'path' : use listpreds from path[-1]
                'list' : use 'list' queryopt
                'view' : use view named by 'view' queryopt
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

        writetags = []
        listtags = []
        
        subjpreds, listpreds, ordertags = path[-1]
        save_listpreds = []
        
        for source in list_priority:
            
            listopt = self.queryopts.get('list')
            viewopt = self.queryopts.get('view')
            view = self.select_view(viewopt)
            default = self.select_view()
            listname = '%s list tags' % list_prefix
            writename = '%s list tags write' % list_prefix
                
            if source == 'path' and listpreds:
                listtags = [ pred.tag for pred in listpreds ]
                save_listpreds = listpreds
                break
            elif source == 'list' and listopt:
                listtags = [ x for x in listtags.split(',') if x ]
                break
            elif source == 'view' and viewopt and view and view.get(listname, []):
                listtags = view.get(listname, [])
                writetags = view.get(writename, [])
                break
            elif source == 'default' and default and view.get(listname, []):
                listtags = default.get(listname, [])
                writetags = view.get(writename, [])
                break
            elif source == 'all':
                listtags = [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() ]
                break

        listpreds = save_listpreds + [ web.Storage(tag=tag,op=None,vals=[]) for tag in extra_tags + listtags ]

        path[-1] = ( subjpreds, listpreds, ordertags )

        limit = self.queryopts.get('limit', 'default')
        if limit == 'none':
            limit = None
        elif type(limit) == type('text'):
            try:
                limit = int(limit)
            except:
                limit = 25
                
        unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True, subjpreds=subjpreds)
        if unique == False:
            versions = 'latest'
        else:
            # unique is True or None
            versions = 'any'

        versions = self.queryopts.get('versions', versions)
        if versions not in [ 'latest', 'any' ]:
            versions = 'latest'
            
        return (path, listtags, writetags, limit, versions)

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

