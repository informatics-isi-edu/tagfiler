import re
import urllib
import web
import psycopg2
import os
import logging
import subprocess
import socket
import datetime
import pytz
import traceback
import distutils.sysconfig
import sys
import string
from logging.handlers import SysLogHandler
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

def urlquote(url):
    "define common URL quote mechanism for registry URL value embeddings"
    return urllib.quote(url, safe="")

def make_filter(allowed):
    allchars = string.maketrans('', '')
    delchars = ''.join([c for c in allchars if c not in allowed])
    return lambda s, a=allchars, d=delchars: (str(s)).translate(a, d)

idquote = make_filter(string.letters + string.digits + '_-:.' )

class WebException (web.HTTPError):
    def __init__(self, status, data='', headers={}):
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
        data = render.Error(status, desc, data)
        WebException.__init__(self, status, headers=headers, data=data)

class Forbidden (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '403 Forbidden'
        desc = 'The requested %s is forbidden.'
        data = render.Error(status, desc, data)
        WebException.__init__(self, status, headers=headers, data=data)

class Unauthorized (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '401 Unauthorized'
        desc = 'The requested %s requires authorization.'
        data = render.Error(status, desc, data)
        WebException.__init__(self, status, headers=headers, data=data)

class BadRequest (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '400 Bad Request'
        desc = 'The request is malformed. %s'
        data = render.Error(status, desc, data)
        WebException.__init__(self, status, headers=headers, data=data)

class Conflict (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '409 Conflict'
        desc = 'The request conflicts with the state of the server. %s'
        data = render.Error(status, desc, data)
        WebException.__init__(self, status, headers=headers, data=data)

class IntegrityError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a integrity error: %s.'
        data = render.Error(status, desc, data)
        WebException.__init__(self, status, headers=headers, data=data)

class RuntimeError (WebException):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a runtime error: %s.'
        data = render.Error(status, desc, data)
        WebException.__init__(self, status, headers=headers, data=data)

class Application:
    "common parent class of all service handler classes to use db etc."
    __slots__ = [ 'dbnstr', 'dbstr', 'db', 'home', 'store_path', 'chunkbytes', 'render', 'typenames', 'help', 'jira', 'remap', 'webauthnexpiremins' ]

    def getParamDb(self, suffix, default=None):
        results = self.getParamsDb(suffix)
        if len(results) == 1:
            return results[0]
        elif len(results) == 0:
            return default
        else:
            raise ValueError

    def getParamsDb(self, suffix):
        results = self.gettagvals('_cfg_%s' % suffix, data_id='tagfiler configuration')
        #web.debug(suffix, results)
        return results

    def __init__(self):
        "store common configuration data for all service classes"
        global render

        myAppName = os.path.basename(web.ctx.env['SCRIPT_NAME'])

        def getParamEnv(suffix, default=None):
            return web.ctx.env.get('%s.%s' % (myAppName, suffix), default)

        def parseBoolString(theString):
            if theString.lower() in [ 'true', 't', 'yes', 'y' ]:
                return True
            else:
                return False
              
        def buildPolicyRules(rules):
            remap = dict()
            for rule in rules:
                rule = tuple(rule.split(','))
                srcrole,dstrole,read,write = rule
                remap[srcrole.strip()] = (dstrole.strip(), parseBoolString(read.strip()), parseBoolString(write.strip()))
            return remap
        
        try:
            p = subprocess.Popen(['/usr/bin/whoami'], stdout=subprocess.PIPE)
            line = p.stdout.readline()
            self.daemonuser = line.strip()
        except:
            self.daemonuser = 'tagfiler'

        self.hostname = socket.gethostname()

        self.dbnstr = getParamEnv('dbnstr', 'postgres')
        self.dbstr = getParamEnv('dbstr', '')
        self.db = web.database(dbn=self.dbnstr, db=self.dbstr)

        t = self.db.transaction()
        
        self.authn = webauthn.providers.AuthnInfo('root', set(['root']), None, None, False, None)
        
        self.store_path = self.getParamDb('store path', '/var/www/%s-data' % self.daemonuser)
        self.log_path = self.getParamDb('log path', '/var/www/%s-logs' % self.daemonuser)
        self.template_path = self.getParamDb('template path',
                                        '%s/tagfiler/templates' % distutils.sysconfig.get_python_lib())
        self.render = web.template.render(self.template_path)
        render = self.render # HACK: make this available to exception classes too

        self.home = self.getParamDb('home', 'https://%s' % self.hostname)
        self.help = self.getParamDb('help')
        self.jira = self.getParamDb('bugs')
        
        self.remap = buildPolicyRules(self.getParamsDb('policy remappings'))
        self.localFilesImmutable = parseBoolString(self.getParamDb('local files immutable', 'False'))
        self.remoteFilesImmutable = False # parseBoolString(self.getParamDb('remote files immutable', 'False'))
        self.webauthnhome = self.getParamDb('webauthn home')
        self.webauthnrequire = parseBoolString(self.getParamDb('webauthn require', 'False'))

        self.chunkbytes = int(self.getParamDb('chunk bytes', 1048576))
        

        self.logo = self.getParamDb('logo', '')
        self.subtitle = self.getParamDb('subtitle', '')
        self.contact = self.getParamDb('contact', None)
        self.appletTest = self.getParamDb('applet test properties', None)
        self.appletlog = self.getParamDb('applet test log', None)
        self.logmsgs = []
        self.middispatchtime = None

        self.filelisttags = self.getParamsDb('file list tags')
        self.filelisttagswrite = self.getParamsDb('file list tags write')
                
        self.customtags = self.getParamsDb('applet tags')
        self.requiredtags = self.getParamsDb('applet tags require')
        self.customproperties = None # self.getParamDb('applet properties', None)

        t.commit()

        self.rfc1123 = '%a, %d %b %Y %H:%M:%S UTC%z'

        # TODO: pull this from database?
        self.typenames = { '' : 'No content',
                           'int8' : 'Integer',
                           'float8' : 'Floating point',
                           'date' : 'Date',
                           'timestamptz' : 'Date and time with timezone',
                           'text' : 'Text',
                           'role' : 'Role' }

        self.dbtypes = { 'int8' : 'int8',
                         'float8' : 'float8',
                         'date' : 'date',
                         'timestamptz' : 'timestamptz',
                         'text' : 'text',
                         'role' : 'text' }

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

        self.validators = { 'owner' : self.validateRole,
                            'read users' : self.validateRolePattern,
                            'write users' : self.validateRolePattern,
                            'modified by' : self.validateRole }

        self.systemTags = ['created', 'modified', 'modified by', 'bytes', 'name', 'url', 'sha256sum']
        self.ownerTags = ['read users', 'write users']

    def validateRole(self, role):
        if self.authn:
            try:
                valid = self.authn.roleProvider.testRole(role)
            except NotImplemented:
                valid = True
            if not valid:
                raise Conflict('Supplied tag value "%s" is not a valid role.' % role)
                
    def validateRolePattern(self, role):
        if role in [ '*' ]:
            return
        return self.validateRole(role)

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

    def renderlist(self, title, renderlist, refresh=True):
        tvars = dict()
        if refresh:
            tvars['pollmins'] = 1

        tvars['title'] = title
        tvars['subtitle'] = self.subtitle
        tvars['logo'] = self.logo

        tvars['home'] = self.home + web.ctx.homepath
        tvars['help'] = self.help
        tvars['bugs'] = self.jira
        tvars['webauthnhome'] = self.webauthnhome
        tvars['webauthnrequire'] = self.webauthnrequire
        tvars['authn'] = self.authn

        return "".join([unicode(r) for r in 
                        [self.render.Top(tvars)] 
                        + renderlist
                        + [self.render.Bottom(tvars)]])

    def preDispatchFake(self, uri, app):
        self.db = app.db
        self.authn = app.authn

    def preDispatch(self, uri):
        if self.webauthnhome:
            if not self.db:
                self.db = web.database(dbn=self.dbnstr, db=self.dbstr)
            self.authn = webauthn.session.test_and_update_session(self.db,
                                                                  referer=self.home + uri,
                                                                  setcookie=True)
            self.middispatchtime = datetime.datetime.now()
            if not self.authn.role and self.webauthnrequire:
                raise web.seeother(self.webauthnhome + '/login?referer=%s' % self.home + uri)
        else:
            try:
                user = web.ctx.env['REMOTE_USER']
                roles = set([ user ])
            except:
                user = None
                roles = set()
            self.authn = webauthn.providers.AuthnInfo(user, roles, None, None, False, None)

    def postDispatch(self, uri=None):
        if self.webauthnhome:
            t = self.db.transaction()
            webauthn.session.test_and_update_session(self.db, self.authn.guid,
                                                     ignoremustchange=True,
                                                     setcookie=False)
            t.commit()

    def midDispatch(self):
        now = datetime.datetime.now()
        if self.middispatchtime == None or (now - self.middispatchtime).seconds > 30:
            self.postDispatch()
            self.middispatchtime = now

    def setNoCache(self):
        now = datetime.datetime.now(pytz.timezone('UTC'))
        now_rfc1123 = now.strftime(self.rfc1123)
        web.header('Cache-control', 'no-cache')
        web.header('Expires', now_rfc1123)

    def dbtransact(self, body, postCommit):
        """re-usable transaction pattern

           using caller-provided thunks under boilerplate
           commit/rollback/retry logic
        """
        if not self.db:
            self.db = web.database(dbn=self.dbnstr, db=self.dbstr)
        count = 0
        limit = 10
        while True:
            t = self.db.transaction()
            self.logmsgs = []
            count = count + 1
            try:
                bodyval = body()
                t.commit()
                break
            # syntax "Type as var" not supported by Python 2.4
            except (NotFound, BadRequest, Unauthorized, Forbidden, Conflict), te:
                t.rollback()
                web.debug(te)
                raise te
            except (psycopg2.DataError, psycopg2.ProgrammingError), te:
                t.rollback()
                web.debug(traceback.format_exception(TypeError, te, sys.exc_info()[2]))
                raise BadRequest(data='Logical error: ' + str(te))
            except TypeError, te:
                t.rollback()
                web.debug(traceback.format_exception(TypeError, te, sys.exc_info()[2]))
                raise RuntimeError(data=str(te))
            except (psycopg2.IntegrityError, IOError), te:
                t.rollback()
                if count > limit:
                    web.debug('exceeded retry limit')
                    web.debug(te)
                    raise IntegrityError(data=str(te))
                # else fall through to retry...
            except:
                t.rollback()
                web.debug('got unknown exception from body in dbtransact')
                raise
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

    def owner(self, data_id=None):
        try:
            results = self.select_file_tag('owner', data_id=data_id, owner='_')
            if len(results) > 0:
                return results[0].value
            else:
                return None
        except:
            return None

    def buildroleinfo(self):
        if self.authn.roleProvider:
            try:
                roleinfo = [ role for role in self.authn.roleProvider.listRoles() ]
                roleinfo.append('*')
                return roleinfo
            except NotImplemented:
                return None
    
    def test_file_authz(self, mode, data_id=None, owner=None):
        """Check whether access is allowed to user given mode and owner.

           True: access allowed
           False: access forbidden
           None: user needs to authenticate to be sure"""
        if data_id == None:
            data_id = self.data_id
        if owner == None:
            owner = self.owner(data_id=data_id)
        try:
            authorized = [ res.value for res in self.select_file_acl(mode, data_id) ]
        except:
            authorized = []
        if owner:
            authorized.append(owner)
        else:
            pass
            # authorized.append('*')  # fall back to public model w/o owner?

        authorized.append('root') # allow root to do everything in case of trouble?

        roles = self.authn.roles.copy()
        if roles:
            roles.add('*')
            if roles.intersection(set(authorized)):
                return True
            else:
                return False
        else:
            return None

    def test_tag_authz(self, mode, tagname=None, user=None, data_id=None, fowner=None):
        """Check whether access is allowed to user given policy_tag and owner.

           True: access allowed
           False: access forbidden
           None: user needs to authenticate to be sure"""
        if data_id == None:
            data_id = self.data_id
        if tagname == None:
            tagname = self.tag_id
        if user == None:
            user = self.authn.role
        if fowner == None and data_id:
            fowner = self.owner(data_id)
        
        try:
            tagdef = self.select_tagdef(tagname)[0]
        except:
            raise BadRequest(data="The tag %s is not defined on this server." % tagname)

        # lookup policy model based on access mode we are checking
        column = dict(read='readpolicy', write='writepolicy')
        model = tagdef[column[mode]]
        # model is in [ anonymous, users, file, fowner, tag, system ]

        if model == 'anonymous':
            return True
        elif model == 'users' and user:
            return True
        elif model == 'system':
            return False
        elif model == 'fowner':
            authorized = [ fowner ]
        elif model == 'file':
            try:
                authorized = [ res.value for res in self.select_file_acl(mode, data_id=data_id) ]
            except:
                authorized = [ ]
            if fowner:
                authorized.append(fowner)
            else:
                pass
                #authorized.append('*') # fall back to public model w/o owner?
        elif model == 'tag':
            try:
                authorized = [ res.value for res in self.select_tag_acl(mode, None, tagname) ]
            except:
                authorized = [ ]
            authorized.append(tagdef.owner)

        authorized.append('root') # allow root to do everything in case of trouble?

        roles = self.authn.roles.copy()
        if roles:
            roles.add('*')
            if roles.intersection(set(authorized)):
                return True
            else:
                return False
        else:
            return None

    def test_tagdef_authz(self, mode, tagname, user=None):
        """Check whether access is allowed."""
        if user == None:
            user = self.authn.role
        try:
            tagdef = self.select_tagdef(tagname)[0]
        except:
            raise BadRequest(data="The tag %s is not defined on this server." % tag_id)
        if mode == 'write':
            if self.authn.roles:
                return tagdef.owner in self.authn.roles
            else:
                return None
        else:
            return True

    def enforce_file_authz(self, mode, data_id=None, local=False, owner=None):
        """Check whether access is allowed and throw web exception if not."""
        if data_id == None:
            data_id = self.data_id
        if mode == 'write':
            if not local:
                try:
                    results = self.select_file_tag('Image Set', data_id=data_id)
                    if len(results) > 0:
                        local = True
                except:
                    pass
            if local and self.localFilesImmutable or not local and self.remoteFilesImmutable:
                raise Forbidden(data="access to immutable dataset %s" % data_id)
        allow = self.test_file_authz(mode, data_id=data_id, owner=owner)
        if allow == False:
            raise Forbidden(data="access to dataset %s" % data_id)
        elif allow == None:
            raise Unauthorized(data="access to dataset %s" % data_id)
        else:
            pass

    def gui_test_file_authz(self, mode, data_id=None, owner=None, local=False):
        status = web.ctx.status
        try:
            self.enforce_file_authz(mode, data_id=data_id, local=local, owner=owner)
            return True
        except:
            web.ctx.status = status
            return False

    def enforce_tag_authz(self, mode, tagname=None, data_id=None):
        """Check whether access is allowed and throw web exception if not."""
        if data_id == None:
            data_id = self.data_id
        fowner = self.owner(data_id=data_id)
        user = self.authn.role
        if tagname == None:
            tagname = self.tag_id
        results = self.select_file(data_id=data_id)
        if len(results) == 0:
            raise NotFound(data="dataset %s" % data_id)
        allow = self.test_tag_authz(mode, tagname, user=user, fowner=fowner, data_id=data_id)
        if allow == False:
            raise Forbidden(data="%s access to tag %s on dataset %s" % (mode, tagname, data_id))
        elif allow == None:
            raise Unauthorized(data="%s access to tag %s on dataset %s" % (mode, tagname, data_id))
        else:
            pass

    def enforce_tagdef_authz(self, mode, tag_id=None):
        """Check whether access is allowed and throw web exception if not."""
        if tag_id == None:
            tag_id = self.tag_id
        user = self.authn.role
        allow = self.test_tagdef_authz(mode, tag_id, user)
        if allow == False:
            raise Forbidden(data="access to tag definition %s" % tag_id)
        elif allow == None:
            raise Unauthorized(data="access to tag definition %s" % tag_id)
        else:
            pass

    def wraptag(self, tagname):
        return '_' + tagname.replace('"','""')

    def gettagvals(self, tagname, data_id=None, owner=None, user=None):
        results = self.select_file_tag(tagname, data_id=data_id, owner=owner, user=user)
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

    def select_file(self, data_id=None):
        if data_id == None:
            data_id = self.data_id
        results = self.db.select('files', where="name = $name", vars=dict(name=data_id))
        return results

    def insert_file(self):
        self.db.query("INSERT INTO files ( name, local, location ) VALUES ( $name, $local, $location )",
                      vars=dict(name=self.data_id, local=self.local, location=self.location))

    def update_file(self):
        self.db.query("UPDATE files SET location = $location, local = $local WHERE name = $name",
                      vars=dict(name=self.data_id, location=self.location, local=self.local))

    def delete_file(self, data_id=None):
        if data_id == None:
            data_id = self.data_id
        self.db.query("DELETE FROM files where name = $name",
                      vars=dict(name=data_id))

    def select_tagdef(self, tagname=None, where=None, order=None, staticauthz=None):
        tables = [ 'tagdefs' ]
        wheres = []
        vars = dict()
        if tagname:
            wheres.append("tagname = $tagname")
            vars['tagname'] = tagname
        if where:
            wheres.append(where)
        if order:
            order = 'ORDER BY ' + order
        else:
            order = ''
        if staticauthz != None:
            user = self.authn.role
            table = dict(read='tagreaders', write='tagwriters')[staticauthz]
            policy = dict(read='readpolicy', write='writepolicy')[staticauthz]
            tables.append("%s USING (tagname)" % table)
            if user != None:
                parts = [ "%s != 'tag'" % policy ]
                r = 0
                for role in self.authn.roles:
                    parts.append("owner = $role%s" % r)
                    parts.append("value = $role%s" % r)
                    vars['role%s' % r] = role
                    r += 1
                wheres.append(" OR ".join(parts))
            else:
                wheres.append("%s != 'tag'" % policy)
                wheres.append("%s != 'fowner'" % policy)
                wheres.append("%s != 'users'" % policy)
        tables = " LEFT OUTER JOIN ".join(tables)
        wheres = " AND ".join([ '(%s)' % where for where in wheres ])
        if wheres:
            wheres = "WHERE %s" % wheres

        query = 'SELECT tagdefs.* FROM %s %s %s' % (tables, wheres, order)
        #web.debug(query)
        return self.db.query(query, vars)
        
    def insert_tagdef(self):
        self.db.query("INSERT INTO tagdefs ( tagname, typestr, readpolicy, writepolicy, multivalue, owner ) VALUES ( $tag_id, $typestr, $readpolicy, $writepolicy, $multivalue, $owner )",
                      vars=dict(tag_id=self.tag_id, typestr=self.typestr, readpolicy=self.readpolicy, writepolicy=self.writepolicy, multivalue=self.multivalue, owner=self.authn.role))

        tabledef = "CREATE TABLE \"%s\"" % (self.wraptag(self.tag_id))
        tabledef += " ( file text REFERENCES files (name) ON DELETE CASCADE"
        indexdef = ''
        if self.dbtypes.get(self.typestr, '') != '':
            tabledef += ", value %s" % (self.dbtypes[self.typestr])
            if self.dbtypes.get(self.typestr, '') == 'text':
                tabledef += " DEFAULT ''"
        if not self.multivalue:
            if self.typestr != '':
                tabledef += ", UNIQUE(file, value)"
                indexdef = 'CREATE INDEX "%s_value_idx"' % (self.wraptag(self.tag_id))
                indexdef += ' ON "%s_value_idx"' % (self.wraptag(self.tag_id))
                indexdef += ' (value)'
            else:
                tabledef += ", UNIQUE(file)"
        tabledef += " )"
        self.db.query(tabledef)
        if indexdef:
            self.db.query(indexdef)

    def delete_tagdef(self):
        self.db.query("DELETE FROM tagdefs WHERE tagname = $tag_id",
                      vars=dict(tag_id=self.tag_id))
        self.db.query("DROP TABLE \"%s\"" % (self.wraptag(self.tag_id)))


    def select_file_tag(self, tagname, value=None, data_id=None, tagdef=None, user=None, owner=None):
        if user == None:
            user = self.authn.role
        if tagdef == None:
            tagdef = self.select_tagdef(tagname)[0]
            
        joins = ''
        wheres = ''

        if tagdef.readpolicy == 'anonymous':
            pass
        elif tagdef.readpolicy == 'users':
            if not user:
                return []
        elif tagdef.readpolicy == 'tag':
            if not self.test_tag_authz('read', tagname, user=user, data_id=data_id, fowner=owner):
                return []
        else:
            if owner == None:
                # only do this if not short-circuited above, to prevent recursion
                owner = self.owner()
            if tagdef.readpolicy == 'fowner':
                if owner and owner != user:
                    return []
            elif tagdef.readpolicy == 'file':
                if  not self.test_file_authz('read', data_id=data_id, owner=owner):
                    return []

        query = "SELECT * FROM \"%s\"" % (self.wraptag(tagname)) 
        query += " WHERE file = $file" 
        if value == '':
            query += " AND value IS NULL ORDER BY VALUE"
        elif value:
            query += " AND value = $value ORDER BY VALUE"
        #web.debug(query)
        if data_id == None:
            data_id = self.data_id
        return self.db.query(query, vars=dict(file=data_id, value=value))

    def select_file_acl(self, mode, data_id=None):
        if data_id == None:
            data_id = self.data_id
        tagname = dict(read='read users', write='write users')[mode]
        query = "SELECT * FROM \"%s\"" % (self.wraptag(tagname)) \
                + " WHERE file = $file"
        vars=dict(file=data_id)
        return self.db.query(query, vars=vars)

    def select_tag_acl(self, mode, user=None, tag_id=None):
        if tag_id == None:
            tag_id = self.tag_id
        table = dict(read='tagreaders', write='tagwriters')[mode]
        wheres = [ 'tagname = $tag_id' ]
        vars = dict(tag_id=tag_id)
        if user:
            wheres.append('value = $user')
            vars['user'] = user
        wheres = " AND ".join(wheres)
        query = "SELECT * FROM \"%s\"" % table + " WHERE %s" % wheres
        #web.debug(query)
        return self.db.query(query, vars=vars)

    def set_tag_acl(self, mode, user, tag_id):
        results = self.select_tag_acl(mode, user, tag_id)
        if len(results) > 0:
            return
        table = dict(read='tagreaders', write='tagwriters')[mode]
        query = "INSERT INTO %s" % table + " (tagname, value) VALUES ( $tag_id, $user )"
        self.db.query(query, vars=dict(tag_id=tag_id, user=user))

    def delete_tag_acl(self, mode, user, tag_id):
        table = dict(read='tagreaders', write='tagwriters')[mode]
        query = "DELETE FROM %s" % table + " WHERE tagname = $tag_id AND value = $user"
        self.db.query(query, vars=dict(tag_id=tag_id, user=user))

    def select_acltags(self, mode):
        table = dict(read='tagreaders', write='tagwriters')[mode]
        query = "SELECT tagname FROM %s" % table + " GROUP BY tagname"
        return self.db.query(query)

    def select_filetags(self, tagname=None, where=None, data_id=None, user=None):
        wheres = []
        vars = dict()
        if data_id == None:
            data_id = self.data_id
        if data_id:
            wheres.append("file = $file")
            vars['file'] = data_id
        if where:
            wheres.append(where)
        if tagname:
            wheres.append("tagname = $tagname")
            vars['tagname'] = tagname

        wheres = ' AND '.join(wheres)
        if wheres:
            wheres = "WHERE " + wheres
        query = "SELECT file, tagname FROM filetags join tagdefs using (tagname) " + wheres \
                + " GROUP BY file, tagname ORDER BY file, tagname"
        #web.debug(query)
        return [ result for result in self.db.query(query, vars=vars)
                 if self.test_tag_authz('read', result.tagname, user, result.file) != False ]

    def delete_file_tag(self, tagname, value=None, data_id=None, owner=None):
        if value or value == '':
            whereval = " AND value = $value"
        else:
            whereval = ""
        if data_id == None:
            data_id = self.data_id
        self.db.query("DELETE FROM \"%s\"" % (self.wraptag(tagname))
                      + " WHERE file = $file" + whereval,
                      vars=dict(file=data_id, value=value))
        results = self.select_file_tag(tagname, data_id=data_id, owner=owner)
        if len(results) == 0:
            # there may be other values tagged still
            self.db.delete("filetags", where="file = $file AND tagname = $tagname",
                           vars=dict(file=data_id, tagname=tagname))

    def set_file_tag(self, tagname, value=None, data_id=None, owner=None):
        validator = self.validators.get(tagname)
        if validator:
            validator(value)
        try:
            results = self.select_tagdef(tagname)
            result = results[0]
            tagtype = result.typestr
            multivalue = result.multivalue
        except:
            raise BadRequest(data="The tag %s is not defined on this server." % tagname)

        if data_id == None:
            data_id = self.data_id

        if not multivalue:
            results = self.select_file_tag(tagname, data_id=data_id, owner=owner)
            if len(results) > 0:
                # drop existing value so we can reinsert one standard way
                self.delete_file_tag(tagname, data_id=data_id)
        else:
            results = self.select_file_tag(tagname, value, data_id=data_id, owner=owner)
            if len(results) > 0:
                # (file, tag, value) already set, so we're done
                return

        if tagtype != '' and value != None:
            query = "INSERT INTO \"%s\"" % (self.wraptag(tagname)) \
                    + " ( file, value ) VALUES ( $file, $value )" 
        else:
            # insert untyped or typed w/ default value...
            query = "INSERT INTO \"%s\"" % (self.wraptag(tagname)) \
                    + " ( file ) VALUES ( $file )"

        #web.debug(query)
        self.db.query(query, vars=dict(file=data_id, value=value))
        
        results = self.select_filetags(tagname, data_id=data_id)
        if len(results) == 0:
            self.db.query("INSERT INTO filetags (file, tagname) VALUES ($file, $tagname)",
                          vars=dict(file=data_id, tagname=tagname))
        else:
            # may already be reverse-indexed in multivalue case
            pass            

    def select_next_transmit_number(self):
        query = "SELECT NEXTVAL ('transmitnumber')"
        result = self.db.query(query)
        return str(result[0].nextval).rjust(9, '0')

    def select_files_by_predlist(self, predlist=None):
        def dbquote(s):
            return s.replace("'", "''")
        
        if predlist == None:
            predlist = self.predlist

        roles = [ r for r in self.authn.roles ]
        if roles:
            roles.append('*')

        tagdefs = dict()
        for pred in predlist:
            # do static checks on each referenced tag at most once
            if not tagdefs.has_key(pred['tag']):
                results = self.select_tagdef(pred['tag'])
                if len(results) == 0:
                    raise BadRequest(data="The tag %s is not defined on this server." % pred['tag'])
                tagdef = results[0]
                if tagdef.readpolicy in ['tag', 'users', 'fowner', 'file']:
                    user = self.authn.role
                    if user == None:
                        raise Unauthorized(data='read of tag "%s"' % tagdef.tagname)
                    if tagdef.readpolicy == 'tag':
                        authorized = [ res.value for res in self.select_tag_acl('read', tag_id=tagdef.tagname) ]
                        authorized.append(tagdef.owner)
                        if not set(roles).intersection(set(authorized)):
                            # warn or return an empty result set since nothing can match?
                            raise Forbidden(data='read of tag "%s"' % tagdef.tagname)
                    # fall off, enforce dynamic security below
                tagdefs[tagdef.tagname] = tagdef

        # also prefetch custom per-file tags
        for tagname in self.filelisttags:
            if not tagdefs.has_key(tagname):
                results = self.select_tagdef(tagname)
                if len(results) == 0:
                    raise BadRequest(data="The tag %s is not defined on this server." % pred['tag'])
                tagdef = results[0]
                tagdefs[tagname] = tagdef

        innertables = ['files',
                       '_owner ON (files.name = _owner.file)']
        outertables = ['', # to trigger generatation of LEFT OUTER JOIN prefix
                       '"_read users" ON (files.name = "_read users".file)']
        selects = ['files.name AS file',
                   'files.local AS local',
                   '_owner.value AS owner']
        groupbys = ['files.name',
                    'files.local',
                    '_owner.value']
        wheres = []
        values = dict()

        roletable = [ "(NULL)" ]  # TODO: make sure this is safe?
        for r in range(0, len(roles)):
            roletable.append("('%s')" % dbquote(roles[r]))
        roletable = ", ".join(roletable)

        outertables.append( '(VALUES %s) AS ownrole (role) ON ("_owner".value = ownrole.role)' % roletable)
        outertables.append( '(VALUES %s) AS readrole (role) ON ("_read users".value = readrole.role)' % roletable)
        wheres.append('ownrole.role IS NOT NULL OR readrole IS NOT NULL')
        
        for p in range(0, len(predlist)):
            pred = predlist[p]
            tag = pred['tag']
            op = pred['op']
            vals = pred['vals']
            tagdef = tagdefs[tag]

            if op == ':not:':
                # not matches if tag column is null or we lack read access to the tag (act as if not there)
                outertables.append('"%s" AS t%s ON (files.name = t%s.file)' % (self.wraptag(tag), p, p))                
                if tagdef.readpolicy == 'fowner':
                    # this tag rule is more restrictive than file or static checks already done
                    wheres.append('t%s.file IS NULL OR (ownrole.role IS NULL)' % p)
                else:
                    # covers all cases where tag is more or equally permissive to file or static checks already done
                    wheres.append('t%s.file IS NULL' % p)
            else:
                # all others match if and only if tag column is not null and we have read access
                # ...and any value constraints are met
                innertables.append('"%s" AS t%s ON (files.name = t%s.file)' % (self.wraptag(tag), p, p))                
                if op and vals and len(vals) > 0:
                    valpreds = []
                    for v in range(0, len(vals)):
                        valpreds.append("t%s.value %s $val%s_%s" % (p, self.opsDB[op], p, v))
                        values["val%s_%s" % (p, v)] = vals[v]
                    wheres.append(" OR ".join(valpreds))
                if tagdef.readpolicy == 'fowner':
                    # this tag rule is more restrictive than file or static checks already done
                    wheres.append('ownrole.role IS NOT NULL' % p)

        # add custom per-file single-val tags to results
        singlevaltags = [ tagname for tagname in self.filelisttags
                          if not tagdefs[tagname].multivalue and tagname != 'owner' ]
        for tagname in singlevaltags:
            outertables.append('"_%s" ON (files.name = "_%s".file)' % (tagname, tagname))
            if tagdefs[tagname].typestr == '':
                selects.append('("_%s".file IS NOT NULL) AS "%s"' % (tagname, tagname))
            else:
                selects.append('"_%s".value AS "%s"' % (tagname, tagname))
            groupbys.append('"%s"' % tagname)

        # add custom per-file multi-val tags to results
        multivaltags = [ tagname for tagname in self.filelisttags
                         if tagdefs[tagname].multivalue ]
        for tagname in multivaltags:
            if tagname != 'read users':
                outertables.append('(SELECT file, array_agg(value) AS value FROM "_%s" GROUP BY file) AS "%s" ON (files.name = "%s".file)' % (tagname, tagname, tagname))
                selects.append('"%s".value AS "%s"' % (tagname, tagname))
                groupbys.append('"%s".value' % tagname)
            else:
                selects.append('(array_agg("_%s".value)) AS "%s"' % (tagname, tagname))

        groupbys = ", ".join(groupbys)
        selects = ", ".join(selects)
        tables = " JOIN ".join(innertables) + " LEFT OUTER JOIN ".join(outertables)

        wheres = " AND ".join([ "(%s)" % where for where in wheres])
        if wheres:
            wheres = "WHERE " + wheres

        query = 'SELECT %s FROM %s %s GROUP BY %s' % (selects, tables, wheres, groupbys)

        query += " ORDER BY files.name"
        
        #web.debug(query)
        #for r in self.db.query('EXPLAIN ANALYZE %s' % query, vars=values):
        #    web.debug(r)
        return self.db.query(query, vars=values)

