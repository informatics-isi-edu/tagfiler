

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

""" Set the logger """
logger = logging.getLogger('tagfiler')

filehandler = logging.FileHandler('/var/www/tagfiler-logs/messages')
fileformatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
filehandler.setFormatter(fileformatter)
logger.addHandler(filehandler)

sysloghandler = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL1)
syslogformatter = logging.Formatter('%(name)s: %(levelname)s: %(message)s')
sysloghandler.setFormatter(syslogformatter)
logger.addHandler(sysloghandler)

logger.setLevel(logging.INFO)

if hasattr(json, 'write'):
    jsonWriter = json.write
elif hasattr(json, 'dumps'):
    jsonWriter = json.dumps
else:
    raise RuntimeError('Could not configure JSON library.')

def urlquote(url):
    "define common URL quote mechanism for registry URL value embeddings"
    if type(url) != type('text'):
        url = str(url)
    return urllib.quote(url, safe="")

def urlunquote(url):
    if type(url) != type('text'):
        url = str(url)
    return urllib.unquote_plus(url)

def parseBoolString(theString):
    if theString.lower() in [ 'true', 't', 'yes', 'y' ]:
        return True
    else:
        return False
              
def predlist_linearize(predlist):
    def pred_linearize(pred):
        vals = [ urlquote(val) for val in pred.vals ]
        vals.sort()
        vals = ','.join(vals)
        if pred.op:
            return '%s%s%s' % (urlquote(pred.tag), pred.op, vals)
        else:
            return '%s' % (urlquote(pred.tag))
    predlist = [ pred_linearize(pred) for pred in predlist ]
    predlist.sort()
    return ';'.join(predlist)

def path_linearize(path):
    def elem_linearize(elem):
        linear = predlist_linearize(elem[0])
        if elem[1]:
            linear += '(%s)' % predlist_linearize(elem[1])
            if elem[2]:
                linear += ','.join(urlquote(elem[2]))
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
        srcrole, dstrole, readers, writers = rule.split(';', 4)
        srcrole = urllib.unquote(srcrole.strip())
        dstrole = urllib.unquote(dstrole.strip())
        readers = readers.strip()
        writers = writers.strip()
        if remap.has_key(srcrole):
            web.debug('Policy rule "%s" duplicates already-mapped source role.' % rule)
            if fatal:
                raise KeyError()
            else:
                continue
        if dstrole == '':
            web.debug('Policy rule "%s" has illegal empty destination role.' % rule)
            if fatal:
                raise ValueError()
            else:
                continue
        if readers != '':
            readers = [ urllib.unquote(reader.strip()) for reader in readers.split(',') ]
            readers = [ reader for reader in readers if reader != '' ]
        else:
            readers = []
        if writers != '':
            writers = [ urllib.unquote(writer.strip()) for writer in writers.split(',') ]
            writers = [ writer for writer in writers if writer != '' ]
        else:
            writers = []
        remap[srcrole] = (dstrole, readers, writers)
    return remap

class WebException (web.HTTPError):
    def __init__(self, status, data='', headers={}, desc='%s'):
        self.detail = urlquote(desc % data)
        #web.debug(self.detail, desc, data)
        data = render.Error(status, desc, data)
        m = re.match('.*MSIE.*',
                     web.ctx.env.get('HTTP_USER_AGENT', 'unknown'))
        if m:
            status = '200 OK'
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class NotFound (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '404 Not Found'
        desc = 'The requested %s could not be found.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class Forbidden (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '403 Forbidden'
        desc = 'The requested %s is forbidden.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class Unauthorized (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '401 Unauthorized'
        desc = 'The requested %s requires authorization.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class BadRequest (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '400 Bad Request'
        desc = 'The request is malformed. %s'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class Conflict (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '409 Conflict'
        desc = 'The request conflicts with the state of the server. %s'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class IntegrityError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a integrity error: %s.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class RuntimeError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a runtime error: %s.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

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
                                    ('policy remappings', []),
                                    ('store path', '/var/www/%s-data' % self.daemonuser),
                                    ('subtitle', ''),
                                    ('logo', ''),
                                    ('tag list tags', []),
                                    ('tagdef write users', []),
                                    ('template path', '%s/tagfiler/templates' % distutils.sysconfig.get_python_lib()),
                                    ('webauthn home', None),
                                    ('webauthn require', 'False') ]

        results = self.select_files_by_predlist(subjpreds=[pred],
                                                listtags=[ "_cfg_%s" % key for key, default in params_and_defaults] + [ pred.tag ],
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

    def select_view(self, viewname=None, default='default'):
        if viewname == None:
            viewname = default
        if viewname == None:
            return None

        view = self.select_config(web.Storage(tag='view', op='=', vals=[viewname]),
                                  [ ('file list tags', []),
                                    ('file list tags write', []),
                                    ('tag list tags', []) ],
                                  fake_missing=False)
        if view == None:
            return self.select_view(default, None)
        else:
            return view
        
    def __init__(self):
        "store common configuration data for all service classes"
        global render

        self.skip_preDispatch = False

        self.version = None
        self.subjpreds = []
        self.globals = dict()

        self.ops = [ ('', 'Tagged'),
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

        self.opsDB = dict([ ('=', '='),
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

        # this ordered list can be pruned to optimize transactions
        self.needed_db_globals = [ 'roleinfo', 'typeinfo', 'typesdict' ]

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

        # static representation of important tagdefs
        self.static_tagdefs = []
        # -- the system tagdefs needed by the select_files_by_predlist call we make below
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
                           ('read users', 'rolepat', True, 'subjectowner', False),
                           ('write users', 'rolepat', True, 'subjectowner', False),
                           ('owner', 'role', False, 'subjectowner', False),
                           ('modified', 'timestamptz', False, 'system', False),
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
            self.static_tagdefs.append(web.Storage(tagname=deftagname,
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

        self.static_tagdefs = dict( [ (tagdef.tagname, tagdef) for tagdef in self.static_tagdefs ] )

        # BEGIN: get runtime parameters from database
        self.globals['tagdefsdict'] = self.static_tagdefs # need these for select_config() below

        # set default anonymous authn info
        self.set_authn(webauthn.providers.AuthnInfo('root', set(['root']), None, None, False, None))

        # get full config
        self.config = self.select_config()
        self.config['policy remappings'] = buildPolicyRules(self.config['policy remappings'])
        
        self.render = web.template.render(self.config['template path'], globals=self.globals)
        render = self.render # HACK: make this available to exception classes too
        
        # 'globals' are local to this Application instance and also used by its templates
        self.globals['smartTagValues'] = True
        self.globals['render'] = self.render # HACK: make render available to templates too
        self.globals['urlquote'] = urlquote
        self.globals['idquote'] = idquote
        self.globals['jsonWriter'] = jsonWriter
        self.globals['subject2identifiers'] = lambda subject, showversions=True: self.subject2identifiers(subject, showversions)

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

        self.rfc1123 = '%a, %d %b %Y %H:%M:%S UTC%z'

        self.tagnameValidators = { 'owner' : self.validateRole,
                                   'read users' : self.validateRolePattern,
                                   'write users' : self.validateRolePattern,
                                   'modified by' : self.validateRole,
                                   'typedef values' : self.validateEnumeration,
                                   '_cfg_policy remappings' : self.validatePolicyRule }
        
        self.tagtypeValidators = { 'tagname' : self.validateTagname,
                                   'file' : self.validateFilename,
                                   'vfile' : self.validateVersionedFilename }

    def validateFilename(self, file, tagname='', subject=None):        
        results = self.select_files_by_predlist(subjpreds=[web.Storage(tag='name', op='=', vals=[file])],
                                                listtags=['id'])
        if len(results) == 0:
            raise Conflict('Supplied file name "%s" for tag "%s" is not found.' % (file, tagname))

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
                raise BadRequest('Supplied versioned file name "%s" for tag "%s" has an invalid version suffix.' % (vfile, tagname))
            if g['data_id'] == '':
                raise BadRequest('Supplied versioned file name "%s" for tag "%s" has an invalid name.' % (vfile, tagname))
            results = self.select_files_by_predlist(subjpreds=[web.Storage(tag='vname', op='=', vals=[vfile]),
                                                              web.Storage(tag='version', op='=', vals=[version])],
                                                    listtags=['id'],
                                                    versions='any')
            if len(results) == 0:
                raise Conflict('Supplied versioned file name "%s" for tag "%s" is not found.' % (vfile, tagname))
        else:
            raise BadRequest('Supplied versioned file name "%s" for tag "%s" has invalid syntax.' % (vfile, tagname))

    def validateTagname(self, tag, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        if tag == '':
            raise Conflict('You must specify a defined tag name to set values for "%s".' % tagname)
        results = self.select_tagdef(tag)
        if len(results) == 0:
            raise Conflict('Supplied tag name "%s" is not defined.' % tag)

    def validateRole(self, role, tagdef=None, subject=None):
        if self.authn:
            try:
                valid = self.authn.roleProvider.testRole(self.db, role)
            except NotImplemented, AttributeError:
                valid = True
            if not valid:
                web.debug('Supplied tag value "%s" is not a valid role.' % role)
                raise Conflict('Supplied tag value "%s" is not a valid role.' % role)
                
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
            raise BadRequest('Supplied enumeration value "%s" does not have key and description fields.' % enum)

        if tagname == 'typedef values':
            results = self.gettagvals('typedef', subject=subject)
            if len(results) == 0:
                raise Conflict('Set the "typedef" tag before trying to set "typedef values".')
            typename = results[0]
            results = self.get_type(typename)
            if len(results) == 0:
                raise Conflict('The type "%s" is not defined!' % typename)
            type = results[0]
            dbtype = type['typedef dbtype']
            try:
                key = self.downcast_value(dbtype, key)
            except:
                raise BadRequest(data='The key "%s" cannot be converted to type "%s" (%s).' % (key, type['typedef description'], dbtype))

    def validatePolicyRule(self, rule, tagdef=None, subject=None):
        tagname = ''
        if tagdef:
            tagname = tagdef.tagname
        try:
            remap = buildPolicyRules([rule], fatal=True)
        except (ValueError, KeyError):
            raise BadRequest('Supplied rule "%s" is invalid for tag "%s".' % (rule, tagname))
        srcrole, mapping = remap.items()[0]
        if self.config['policy remappings'].has_key(srcrole):
            raise BadRequest('Supplied rule "%s" duplicates already mapped source role "%s".' % (rule, srcrole))

    def doPolicyRule(self, newfile):
        srcroles = set(self.config['policy remappings'].keys()).intersection(self.authn.roles)
        if len(srcroles) == 1:
            try:
                t = self.db.transaction()
                srcrole = srcroles.pop()
                dstrole, readusers, writeusers = self.config['policy remappings'][srcrole]
                #web.debug(self.remap)
                #web.debug('remap:', self.remap[srcrole])
                self.delete_tag(newfile, self.globals['tagdefsdict']['read users'])
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
            raise Conflict("Ambiguous remap rules encountered.")

    def logfmt(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        parts = []
        if dataset:
            parts.append('dataset "%s"' % dataset)
        if tag:
            parts.append('tag "%s"' % tag)
        if value:
            parts.append('value "%s"' % value)
        if mode:
            parts.append('mode "%s"' % mode)
        if not self.authn.role:
            user = 'anonymous'
        else:
            user = self.authn.role
        return ('%s ' % action) + ', '.join(parts) + ' by user "%s"' % user

    def log(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        logger.info(self.logfmt(action, dataset, tag, mode, user, value))

    def txlog(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        self.logmsgs.append(self.logfmt(action, dataset, tag, mode, user, value))

    def set_authn(self, authn):
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
        self.globals['tagdefsdict'] = dict ([ (tagdef.tagname, tagdef) for tagdef in self.select_tagdef() ])

    def preDispatchCore(self, uri, setcookie=True):
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
        self.globals['tagdefsdict'] = dict ([ (tagdef.tagname, tagdef) for tagdef in self.select_tagdef() ])

    def preDispatch(self, uri):
        def body():
            self.preDispatchCore(uri)

        def postCommit(results):
            pass

        if not self.skip_preDispatch:
            self.dbtransact(body, postCommit)

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
        now_rfc1123 = now.strftime(self.rfc1123)
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
            limit = 10
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
                                               typeinfo=lambda : self.get_type(),
                                               typesdict=lambda : dict([ (type['typedef'], type) for type in self.globals['typeinfo'] ]))
                        for key in self.needed_db_globals:
                            self.globals[key] = db_globals_dict[key]()

                        def tagOptions(tagname, values=[]):
                            tagdef = self.globals['tagdefsdict'][tagname]
                            tagnames = self.globals['tagdefsdict'].keys()
                            type = self.globals['typesdict'][tagdef.typestr]
                            typevals = type['typedef values']
                            roleinfo = self.globals['roleinfo']
                            if tagdef.typestr in ['role', 'rolepat', 'tagname'] or typevals:
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
                        self.logException('web error in transaction body')
                        raise te
                    except (psycopg2.DataError, psycopg2.ProgrammingError), te:
                        t.rollback()
                        self.logException('database error in transaction body')
                        raise BadRequest(data='Logical error: %s.' % str(te))
                    except TypeError, te:
                        t.rollback()
                        self.logException('programming error in transaction body')
                        raise RuntimeError(data=str(te))
                    except (psycopg2.IntegrityError), te:
                        t.rollback()
                        error = str(te)
                        #m = re.match('duplicate key[^"]*"_version_[^"]*key"', error)
                        #if not m or count > limit:
                        #web.debug('IntegrityError', error)
                        if count > limit:
                            # retry on version key violation, can happen under concurrent uploads
                            self.logException('integrity error during transaction body')
                            raise IntegrityError(data=error)
                    except (IOError), te:
                        t.rollback()
                        error = str(te)
                        if count > limit:
                            self.logException('too many retries during transaction body')
                            raise RuntimeError(data=error)
                        # else fall through to retry...
                    except:
                        t.rollback()
                        self.logException('unmatched error in transaction body')
                        raise

                except psycopg2.InterfaceError:
                    # try reopening the database connection
                    self.db = web.database(db=self.dbstr, dbn=self.dbnstr)

                # exponential backoff...
                # count=1 is roughly 0.1 microsecond
                # count=9 is roughly 10 seconds
                # randomly jittered from 75-125% of exponential delay
                delay =  random.uniform(0.75, 1.25) * math.pow(10.0, count) * 0.00000001
                web.debug('transaction retry: delaying %f' % delay)
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
                raise Conflict('Tag "%s" referenced in subject predicate list is not defined on this server.' % pred.tag)

            if restrictSchema:
                if tagdef.tagname not in [ 'name', 'version' ] and tagdef.writeok == False:
                    raise Conflict('Subject predicate sets restricted tag "%s".' % tagdef.tagname)
                if tagdef.typestr == 'empty' and pred.op or \
                       tagdef.typestr != 'empty' and pred.op != '=':
                    raise Conflict('Subject predicate has inappropriate operator "%s" on tag "%s".' % (pred.op, tagdef.tagname))
                    
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
            raise Conflict('Subject-identifying predicate list requires a unique identifying constraint.')

    def test_file_authz(self, mode, subject):
        """Check whether access is allowed to user given mode and owner.

           True: access allowed
           False: access forbidden
           None: user needs to authenticate to be sure"""
        status = web.ctx.status

        # read is authorized or subject would not be found
        if subject['write users'] == None:
            subject['write users'] = []
        if mode == 'write':
            if len(set(subject.get('%s users' % mode, []))
                   .union(set(['*']))
                   .intersection(set(subject['write users']))) > 0:
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
           None: user needs to authenticate to be sure"""
        if tagdef[mode + 'ok']:
            return True
        elif tagdef[mode + 'ok'] == None:
            if tagdef[mode + 'policy'] == 'subject' and dict(read=True, write=subject.writeok)[mode]:
                return True
            elif tagdef[mode + 'policy']  == 'subjectowner' and subject.owner in self.authn.roles:
                return True
        if self.authn == None:
            return None
        else:
            return False

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
            raise Forbidden(data=data)
        elif allow == None:
            raise Unauthorized(data=data)

    def enforce_tag_authz(self, mode, subject, tagdef):
        """Check whether access is allowed and throw web exception if not."""
        allow = self.test_tag_authz(mode, subject, tagdef)
        data = '%s of tag "%s" on dataset "%s"' % (mode, tagdef.tagname, self.subject2identifiers(subject)[0])
        if allow == False:
            raise Forbidden(data=data)
        elif allow == None:
            raise Unauthorized(data=data)

    def enforce_tagdef_authz(self, mode, tagdef):
        """Check whether access is allowed and throw web exception if not."""
        allow = self.test_tagdef_authz(mode, tagdef)
        data = '%s of tagdef="%s"' % (mode, tagdef.tagname)
        if allow == False:
            raise Forbidden(data=data)
        elif allow == None:
            raise Unauthorized(data=data)

    def wraptag(self, tagname, suffix='', prefix='_'):
        return '"' + prefix + tagname.replace('"','""') + suffix + '"'

    def classify_subject(self, subject):
        datapred = None
        for dtype in [ 'file', 'url', 'tagdef', 'typedef', 'config', 'view' ]:
            keyv = subject.get(dtype, None)
            if keyv:
                return dtype
        return None

    def subject2identifiers(self, subject, showversions=True):
        dtype = self.classify_subject(subject)
        if dtype in [ 'tagdef', 'typedef', 'config', 'view' ]:
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
        listtags = [ 'typedef', 'typedef description', 'typedef dbtype', 'typedef values' ]
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
                       'tag write users': 'tagwriters' }

    def select_tagdef(self, tagname=None, subjpreds=[], order=None, enforce_read_authz=True):
        listtags = [ 'owner' ]
        listtags = listtags + Application.tagdef_listas.keys()

        if order:
            ordertags = [ order ]
        else:
            ordertags = []

        def add_authz(tagdef):
            def compute_authz(mode, tagdef):
                policy = tagdef['%spolicy' % mode]
                if policy == 'system':
                    return False
                elif policy in [ 'subjectowner', 'subject' ]:
                    return None
                elif policy == 'tag':
                    return tagdef.owner in self.authn.roles \
                           or len(set(self.authn.roles)
                                  .union(set(['*']))
                                  .intersection(set(tagdef['tag' + mode[0:4] + 'ers'] or []))) > 0
                elif policy == 'users':
                    return self.authn.role != None
                else:
                    # policy == 'anonymous'
                    return True
            
            for mode in ['read', 'write']:
                tagdef['%sok' % mode] = compute_authz(mode, tagdef)

            return tagdef
            
        if tagname:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op='=', vals=[tagname]) ]
        else:
            subjpreds = subjpreds + [ web.Storage(tag='tagdef', op=None, vals=[]) ]

        results = [ add_authz(tagdef) for tagdef in self.select_files_by_predlist(subjpreds, listtags, ordertags, listas=Application.tagdef_listas, tagdefs=self.static_tagdefs, enforce_read_authz=enforce_read_authz) ]
        #web.debug(results)
        return results

    def insert_tagdef(self):
        results = self.select_tagdef(self.tag_id)
        if len(results) > 0:
            raise Conflict('Tagdef "%s" already exists. Delete it before redefining.' % self.tag_id)

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
            raise BadRequest('Referenced type "%s" is not defined.' % tagdef.typestr)

        dbtype = type['typedef dbtype']
        if dbtype != '':
            tabledef += ", value %s" % dbtype
            if dbtype == 'text':
                tabledef += " DEFAULT ''"
            tabledef += ' NOT NULL'
            
            if tagdef.typestr == 'file':
                tabledef += ' REFERENCES "_latest with name" (value) ON DELETE CASCADE'
            elif tagdef.typestr == 'vfile':
                tabledef += ' REFERENCES "_vname" (value) ON DELETE CASCADE'
                
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
        if tagdef.readok == False or (tagdef.readok == None and subject.owner not in self.authn.roles):
            raise Forbidden('read access to /tags/%s(%s)' % (self.subject2identifiers(subject)[0], tagdef.tagname))
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

        query = 'DELETE FROM %s AS tag' % self.wraptag(tagdef.tagname) + wheres
        vars=dict(id=subject.id, value=value, tagname=tagdef.tagname)
        self.db.query(query, vars=vars)

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
            raise Conflict('The tag definition references a field type "%s" which is not defined!' % typestr)
        dbtype = typedef['typedef dbtype']
        
        validator = self.tagnameValidators.get(tagdef.tagname)
        if validator:
            validator(value, tagdef, subject)

        validator = self.tagtypeValidators.get(typedef.typedef)
        if validator:
            validator(value, tagdef, subject)

        try:
            if value:
                value = self.downcast_value(dbtype, value)
        except:
            raise BadRequest(data='The value "%s" cannot be converted to stored type "%s".' % (value, dbtype))

        if tagdef.unique:
            results = self.select_tag_noauthn(None, tagdef, value)
            if len(results) > 0 and results[0].subject != subject.id:
                if tagdef.typestr != 'empty':
                    raise Conflict('Tag "%s" is defined as unique and value "%s" is already bound to another subject.' % (tagdef.tagname, value))
                else:
                    raise Conflict('Tag "%s" is defined as unique is already bound to another subject.' % (tagdef.tagname))

        if not tagdef.multivalue:
            results = self.select_tag_noauthn(subject, tagdef)
            if len(results) > 0:
                if dbtype == '' or results[0].value == value:
                    return
                else:
                    self.delete_tag(subject, tagdef)
        else:
            results = self.select_tag_noauthn(subject, tagdef, value)
            if len(results) > 0:
                # (file, tag, value) already set, so we're done
                return

        if dbtype != '' and value != None:
            query = 'INSERT INTO %s' % self.wraptag(tagdef.tagname) \
                    + ' (subject, value) VALUES ($subject, $value)'
        else:
            # insert untyped or typed w/ default value...
            query = 'INSERT INTO %s' % self.wraptag(tagdef.tagname) \
                    + ' (subject) VALUES ($subject)'

        vars = dict(subject=subject.id, value=value, tagname=tagdef.tagname)
        #web.debug(query, vars)
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

    def build_select_files_by_predlist(self, subjpreds=None, listtags=None, ordertags=[], id=None, version=None, qd=0, versions='latest', listas=None, tagdefs=None, enforce_read_authz=True, limit=None, assume_roles=False, listpreds=None):

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
                raise BadRequest(data='The tag "%s" is not defined on this server.' % tagname)

        innertables = []  # (table, alias)
        innertables_special = []
        outertables = [('_owner', None)]
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
                    raise Conflict('The "id" tag is bound for all catalog entries and is non-sensical to use with the :not: operator.')
                outertables.append((self.wraptag(tag), 't%s' % p ))
                if tagdef.readok == False and enforce_read_authz:
                    # this tag cannot be read so act like it is absent
                    wheres.append('True')
                elif tagdef.readpolicy == 'subjectowner' and enforce_read_authz:
                    # this tag rule is more restrictive than file or static checks already done
                    # act like it is NULL if user isn't allowed to read this tag
                    outertables_special.append( 'roles AS ownerrole_%d ON (_owner.value = ownerrole_%d.role)' % (p, p) )
                    wheres.append('t%s.subject IS NULL OR (ownerrole_%d.role IS NULL)' % (p, p))
                else:
                    # covers all cases where tag is more or equally permissive to file or static checks already done
                    wheres.append('t%s.subject IS NULL' % p)
            elif op == 'IN':
                # special internal operation to restrict by sub-query, doesn't need to be sanity checked
                if tag == 'id':
                    wheres.append('subject IN (%s)' % (vals))
                else:
                    innertables.append((self.wraptag(tag), 't%s' % p))
                    wheres.append('t%s.value IN (%s)' % (p, vals))
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
                                    
                    if tag != 'id':
                        innertables.append((self.wraptag(tag), 't%s' % p))

                    if op and vals and len(vals) > 0:
                        valpreds = []
                        for v in range(0, len(vals)):
                            if tag != 'id':
                                valpreds.append("t%s.value %s $val%s_%s_%d" % (p, self.opsDB[op], p, v, qd))
                            else:
                                valpreds.append("subject %s $val%s_%s_%d" % (self.opsDB[op], p, v, qd))
                            values["val%s_%s_%d" % (p, v, qd)] = vals[v]
                        wheres.append(" OR ".join(valpreds))
                    

        outertables_special.append( 'roles AS readerrole ON ("_read users".value = readerrole.role)' )
        if enforce_read_authz:
            if need_subjectowner_test:
                # at least one predicate test requires subjectowner-based read access rights
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
            
        # compute file write access rights for later consumption
        outertables_special.append( 'roles AS writerrole ON ("_write users".value = writerrole.role)' )
        selects.append('bool_or(ownerrole.role IS NOT NULL OR writerrole.role IS NOT NULL) AS writeok')

        if id:
            # special single-entry lookup
            values['id_%d' % qd] = id
            wheres.append("subject = $id_$d" % qd)

        # constrain to latest named files ONLY
        if versions == 'latest':
            outertables.append(('"_latest with name"', None))
            outertables.append(('_name', None))
            wheres.append('"_name".value IS NULL OR "_latest with name".value IS NOT NULL')

        outertables = outertables \
                      + [('_owner', None),
                         ('"_read users"', None),
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

        # this query produces a set of (subject, owner, readok, writeok) rows that match the query result set
        subject_query = 'SELECT %s' % ','.join(selects) \
                        + ' FROM %s' % ' LEFT OUTER JOIN '.join([' JOIN '.join(innertables2)] + outertables2 ) \
                        + ' WHERE %s' % ' AND '.join([ '(%s)' % where for where in wheres ]) \
                        + ' GROUP BY subject, owner'

        # now build the outer query that attaches listtags metadata to results
        core_tags = dict(owner='subjects.owner',
                         id='subjects.subject')
        
        selects = [ 'subjects.readok AS readok', 'subjects.writeok AS writeok' ]
        innertables = [('(%s)' % subject_query, 'subjects')]
        outertables = []
        groupbys = [ 'subjects.readok', 'subjects.writeok' ]

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
                        raise BadRequest('Inappropriate operator "%s" for tag "%s".' % (pred.op, pred.tag))
                    valpreds = []
                    for v in range(0, len(pred.vals)):
                        valpreds.append( '%s %s $listval_%s_%d_%d' % (vref, self.opsDB[pred.op], t, p, v) )
                        values['listval_%s_%d_%d' % (t, p, v)] = pred.vals[v]
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
                elif tagdef.readpolicy == 'subject':
                    # we can read this tag for any subject we can read
                    # which is all subjects being read, when we are enforcing
                    pass
                elif tagdef.readpolicy == 'subjectowner':
                    # need to condition read on subjectowner test
                    expr = 'CASE WHEN ownerrole.role IS NOT NULL THEN %s ELSE NULL END' % expr
                else:
                    raise RuntimeError('Unimplemented list-tags authorization scenario in query by predlist for tag "%s".', tagdef.tagname)
                
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

    def build_files_by_predlist_path(self, path=None, versions='latest', limit=None, enforce_read_authz=True):
        values = dict()
        tagdefs = self.globals['tagdefsdict']
        
        def build_query_recursive(stack, qd, limit):
            subjpreds, listpreds, ordertags = stack[0]
            subjpreds = [ p for p in subjpreds ]
            if len(stack) == 1:
                # this query element is not contextualized
                q, v = self.build_select_files_by_predlist(subjpreds, ordertags, qd=qd, versions=versions, tagdefs=tagdefs, limit=limit, assume_roles=qd!=0, listpreds=listpreds, enforce_read_authz=enforce_read_authz)
                values.update(v)
                return q
            else:
                # this query element is contextualized
                cstack = stack[1:]
                csubjpreds, clistpreds, cordertags = cstack[0]
                
                if len(clistpreds) != 1:
                    raise BadRequest("Path context %d has ambiguous projection with %d elements." % (len(cstack)-1, len(clistpreds)))
                projection = clistpreds[0].tag
                if tagdefs[projection].typestr not in [ 'text', 'file', 'vfile', 'id', 'tagname', 'viewname' ]:
                    raise BadRequest('Projection tag "%s" does not have a valid type to be used as a file context.' % projection)
                
                context_attr = dict(text='name', file='name', vfile='vname', id='id', viewname='view', tagname='tagdef')[tagdefs[projection].typestr]
                if tagdefs[projection].multivalue:
                    projectclause = 'unnest("%s")' % projection
                else:
                    projectclause = '"%s"' % projection
                    
                cstack[0] = csubjpreds, clistpreds, None # don't bother sorting context more than necessary
                cq = build_query_recursive(cstack, qd + 1, limit=None)
                cq = "SELECT DISTINCT %s FROM (%s) AS context_%d" % (projectclause, cq, qd) # gives set of context values
                
                subjpreds.append( web.Storage(tag=context_attr, op='IN', vals=cq) )  # use special predicate IN with sub-query expression
                q, v = self.build_select_files_by_predlist(subjpreds, ordertags, qd=qd, versions=versions, tagdefs=tagdefs, limit=limit, assume_roles=qd!=0, listpreds=listpreds, enforce_read_authz=enforce_read_authz)
                values.update(v)
                return q
        
        if path == None:
            path = [ ([], [], []) ]

        # query stack is path in reverse... final result element in front, projected context behind
        stack = [ e for e in path ]
        stack.reverse()

        query = build_query_recursive(stack, qd=0, limit=limit)

        #web.debug(query, values)
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
                
        unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True)
        if unique == False:
            versions = 'latest'
        else:
            # unique is True or None
            versions = 'any'

        versions = self.queryopts.get('versions', versions)
        if versions not in [ 'latest', 'any' ]:
            versions = 'latest'

        return (path, listtags, writetags, limit, versions)

    
