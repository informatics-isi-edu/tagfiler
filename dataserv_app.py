import urllib
import web
import psycopg2
import os
import logging
import datetime
import traceback
import sys
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
logger.addHandler(SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL1))
logger.setLevel(logging.INFO)

def urlquote(url):
    "define common URL quote mechanism for registry URL value embeddings"
    return urllib.quote(url, safe="")

class NotFound (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '404 Not Found'
        desc = 'The requested %s could not be found.'
        data = render.Error(status, desc, data)
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class Forbidden (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '403 Forbidden'
        desc = 'The requested %s is forbidden.'
        web.debug(desc % data)
        data = render.Error(status, desc, data)
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class Unauthorized (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '401 Unauthorized'
        desc = 'The requested %s requires authorization.'
        data = render.Error(status, desc, data)
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class BadRequest (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '400 Bad Request'
        desc = 'The request is malformed. %s'
        data = render.Error(status, desc, data)
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class Conflict (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '409 Conflict'
        desc = 'The request conflicts with the state of the server. %s'
        data = render.Error(status, desc, data)
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class IntegrityError (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a integrity error: %s.'
        data = render.Error(status, desc, data)
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class RuntimeError (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        status = '500 Internal Server Error'
        desc = 'The request execution encountered a runtime error: %s.'
        data = render.Error(status, desc, data)
        web.HTTPError.__init__(self, status, headers=headers, data=data)

class Application:
    "common parent class of all service handler classes to use db etc."
    __slots__ = [ 'dbnstr', 'dbstr', 'db', 'home', 'store_path', 'chunkbytes', 'render', 'typenames', 'help', 'jira', 'remap' ]

    def __init__(self):
        "store common configuration data for all service classes"
        global render

        myAppName = os.path.basename(web.ctx.env['SCRIPT_NAME'])

        def getParam(suffix, default=None):
            return web.ctx.env.get('%s.%s' % (myAppName, suffix), default)

        def parseBoolString(theString):
            if theString[0].upper() == 'T':
                return True
            else:
                return False
              
        def getPolicyRules(rules):
            remap = dict()
            if rules:
                rules = rules.split(';')
                for rule in rules:
                    rule = tuple(rule.split(','))
                    srcrole,dstrole,read,write = rule
                    remap[srcrole.strip()] = (dstrole.strip(), parseBoolString(read.strip()), parseBoolString(write.strip()))
            return remap

        self.help = getParam('help')
        self.jira = getParam('jira')
        self.remap = getPolicyRules(getParam('policyrules', None))
        self.dbnstr = getParam('dbnstr', 'postgres')
        self.dbstr = getParam('dbstr', '')
        self.home = getParam('home')
        self.store_path = getParam('store_path')
        self.template_path = getParam('template_path')
        self.chunkbytes = int(getParam('chunkbytes', 1048576))
        self.webauthnhome = getParam('webauthnhome')
        self.webauthnrequire = getParam('webauthnrequire')
        self.webauthnexpiremins = int(getParam('webauthnexpiremins', 10))
        self.webauthnrotatemins = int(getParam('webauthnrotatemins', 120))
        self.db = None
        
        if self.webauthnrequire and self.webauthnrequire.lower() in ['t', 'true', 'y', 'yes', '1']:
            self.webauthnrequire = True
        else:
            self.webauthnrequire = False

        self.role = None
        self.roles = set([])
        self.loginsince = None
        self.loginuntil = None

        self.render = web.template.render(self.template_path)
        render = self.render # HACK: make this available to exception classes too

        # TODO: pull this from database?
        self.typenames = { '' : 'No content', 'int8' : 'Integer', 'float8' : 'Floating point',
                           'date' : 'Date', 'timestamptz' : 'Date and time with timezone',
                           'text' : 'Text' }

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

        self.systemTags = ['created', 'modified', 'modified by', 'owner', 'bytes', 'name', 'url']
        self.ownerTags = ['read users', 'write users']

    def log(self, action, dataset=None, tag=None, mode=None, user=None, value=None):
        parts = []
        if dataset:
            parts.append('dataset "%s"' % dataset)
        if tag:
            parts.append('tag "%s"' % tag)
        if value:
            parts.append('value "%s"' % value)
        if mode:
            parts.append('mode "%s"' % mode)
        if not user:
            user = self.user()
        logger.info('tagfiler: %s ' % action + ', '.join(parts) + ' by user "%s"' % user)
        
    def renderlist(self, title, renderlist):
        return "".join([unicode(r) for r in 
                        [self.render.Top(self.home + web.ctx.homepath, title, self.user(), self.loginsince, self.loginuntil, self.webauthnhome, self.help)] + renderlist + [self.render.Bottom()]])

    def preDispatch(self, uri):
        if self.webauthnhome:
            if not self.db:
                self.db = web.database(dbn=self.dbnstr, db=self.dbstr)
            authn = webauthn.session.test_and_update_session(self.db,
                                                             expireperiod=datetime.timedelta(minutes=self.webauthnexpiremins),
                                                             rotateperiod=datetime.timedelta(minutes=self.webauthnrotatemins),
                                                             referer=self.home + uri)
            if authn:
                self.role, self.roles, self.loginsince, self.loginuntil, mustchange = authn
            elif self.webauthnrequire:
                raise web.seeother(self.webauthnhome + '/login?referer=%s' % self.home + uri)

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
        return [ pair[1]
                 for pair in
                 sorted([ self.acceptPair(s) for s in web.ctx.env['HTTP_ACCEPT'].lower().split(',') ],
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

    def user(self):
        try:
            if self.webauthnhome:
                user = self.role
            else:
                user = web.ctx.env['REMOTE_USER']
                self.roles = set([ user ])
        except:
            return None
        return user

    def test_file_authz(self, mode, data_id=None, owner=None):
        """Check whether access is allowed to user given mode and owner.

           True: access allowed
           False: access forbidden
           None: user needs to authenticate to be sure"""
        user = self.user() # initializes self.roles if needed...
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

        roles = self.roles.copy()
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
            user = self.user() # initializes self.roles if needed...
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
                authorized = [ res.value for res in self.select_tag_acl(mode, user, tagname) ]
            except:
                authorized = [ ]
            authorized.append(tagdef.owner)

        authorized.append('root') # allow root to do everything in case of trouble?

        roles = self.roles.copy()
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
            user = self.user()
        try:
            tagdef = self.select_tagdef(tagname)[0]
        except:
            raise BadRequest(data="The tag %s is not defined on this server." % tag_id)
        if mode == 'write':
            if self.roles:
                return tagdef.owner in self.roles
            else:
                return None
        else:
            return True

    def enforce_file_authz(self, mode):
        """Check whether access is allowed and throw web exception if not."""
        allow = self.test_file_authz(mode)
        if allow == False:
            raise Forbidden(data="access to dataset %s" % self.data_id)
        elif allow == None:
            raise Unauthorized(data="access to dataset %s" % self.data_id)
        else:
            pass

    def enforce_tag_authz(self, mode, tagname=None, data_id=None):
        """Check whether access is allowed and throw web exception if not."""
        if data_id == None:
            data_id = self.data_id
        fowner = self.owner(data_id=data_id)
        user = self.user()
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
        user = self.user()
        allow = self.test_tagdef_authz(mode, tag_id, user)
        if allow == False:
            raise Forbidden(data="access to tag definition %s" % tag_id)
        elif allow == None:
            raise Unauthorized(data="access to tag definition %s" % tag_id)
        else:
            pass

    def wraptag(self, tagname):
        return '_' + tagname.replace('"','""')

    def gettagvals(self, tagname, data_id=None, owner=None):
        results = self.select_file_tag(tagname, data_id=data_id, owner=owner)
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

    def delete_file(self):
        self.db.query("DELETE FROM files where name = $name",
                      vars=dict(name=self.data_id))

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
            user = self.user()
            table = dict(read='tagreaders', write='tagwriters')[staticauthz]
            policy = dict(read='readpolicy', write='writepolicy')[staticauthz]
            tables.append("%s USING (tagname)" % table)
            if user != None:
                wheres.append("%s != 'tag' OR owner = $user OR value = $user" % policy)
                vars['user'] = user
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
                      vars=dict(tag_id=self.tag_id, typestr=self.typestr, readpolicy=self.readpolicy, writepolicy=self.writepolicy, multivalue=self.multivalue, owner=self.user()))

        tabledef = "CREATE TABLE \"%s\"" % (self.wraptag(self.tag_id))
        tabledef += " ( file text REFERENCES files (name) ON DELETE CASCADE"
        if self.typestr != '':
            tabledef += ", value %s" % (self.typestr)
        if not self.multivalue:
            if self.typestr != '':
                tabledef += ", UNIQUE(file, value)"
            else:
                tabledef += ", UNIQUE(file)"
        tabledef += " )"
        self.db.query(tabledef)

    def delete_tagdef(self):
        self.db.query("DELETE FROM tagdefs WHERE tagname = $tag_id",
                      vars=dict(tag_id=self.tag_id))
        self.db.query("DROP TABLE \"%s\"" % (self.wraptag(self.tag_id)))


    def select_file_tag(self, tagname, value=None, data_id=None, tagdef=None, user=None, owner=None):
        if user == None:
            user = self.user()
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
                if  not self.test_file_authz('read', owner=owner):
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

    def select_tag_acl(self, mode, tag_id=None):
        if tag_id == None:
            tag_id = self.tag_id
        table = dict(read='tagreaders', write='tagwriters')[mode]
        wheres = [ 'tagname = $tag_id' ]
        vars = dict(tag_id=tag_id)
        wheres = " AND ".join(wheres)
        query = "SELECT * FROM \"%s\"" % table + " WHERE %s" % wheres
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
        if value == '':
            whereval = " AND value IS NULL"
        elif value:
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

    def set_file_tag(self, tagname, value, data_id=None, owner=None):
        try:
            results = self.select_tagdef(tagname)
            result = results[0]
            tagtype = result.typestr
            multivalue = result.multivalue
        except:
            raise BadRequest(data="The tag %s is not defined on this server." % tag_id)

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

        if value:
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

    def select_files_by_predlist(self, predlist=None):
        if predlist == None:
            predlist = self.predlist

        tagdefs = dict()
        for pred in predlist:
            results = self.select_tagdef(pred['tag'])
            if len(results) == 0:
                raise BadRequest(data="The tag %s is not defined on this server." % pred['tag'])
            tagdef = results[0]
            if tagdef.readpolicy in ['tag', 'users', 'fowner', 'file']:
                user = self.user()
                if user == None:
                    raise Unauthorized(data='read of tag "%s"' % tagdef.tagname)
                if tagdef.readpolicy == 'tag':
                    authorized = [ res.value for res in self.select_tag_acl('read', tag_id=tagdef.tagname) ]
                    authorized.append(tagdef.owner)
                    roles = self.roles.copy()
                    if roles:
                        roles.add('*')
                    if not roles.intersection(set(authorized)):
                        # this is statically known, so either warn user (friendly)
                        # or return an empty result set since nothing can match?
                        raise Forbidden(data='read of tag "%s"' % tagdef.tagname)
            tagdefs[tagdef.tagname] = tagdef

        tables = ['files', '_owner ON (files.name = _owner.file)']
        excepttables = ['files', '_owner ON (files.name = _owner.file)'] # only gets used if others are appended
        wheres = []
        exceptwheres = []
        values = dict()

        readclauses = []
        rn = 0
        roles = self.roles.copy()
        if roles:
            roles.add('*')
        for role in roles:
            readclauses.append('_owner.value = $r%s' % rn)
            readclauses.append('"_read users".value = $r%s' % rn)
            values['r%s' % rn] = role
            rn += 1
        readclauses = " OR ".join(readclauses)

        for p in range(0, len(predlist)):
            pred = predlist[p]
            tag = pred['tag']
            op = pred['op']
            vals = pred['vals']
            tagdef = tagdefs[tag]
            if op == ':not:':
                # a non-NULL match excludes the file, but only if user can see that match
                excepttables.append('"%s" AS t%s ON (files.name = t%s.file)' % (self.wraptag(tag), p, p))
                if tagdef.readpolicy == 'fowner':
                    exceptwheres.append('t%s.file IS NOT NULL AND _owner.value = $client' % p)
                elif tagdef.readpolicy == 'file':
                    # note this case is irrelevant because user cannot find files they cannot read
                    # but here for documentation purposes, in case that rule is relaxed
                    exceptwheres.append('t%s.file IS NOT NULL AND (%s)' % (p, readclauses))
                else:
                    exceptwheres.append('t%s.file IS NOT NULL' % p)
            else:
                tables.append('"%s" AS t%s ON (files.name = t%s.file)' % (self.wraptag(tag), p, p))
                if op and vals and len(vals) > 0:
                    valpreds = []
                    for v in range(0, len(vals)):
                        valpreds.append("t%s.value %s $val%s_%s" % (p, self.opsDB[op], p, v))
                        values["val%s_%s" % (p, v)] = vals[v]
                    wheres.append(" OR ".join(valpreds))
                # a predicate matches only if tag is present and value constraints are met
                # but only if user can see that match
                if tagdef.readpolicy == 'fowner':
                    wheres.append('_owner.value = $client')
                elif tagdef.readpolicy == 'file':
                    # note this case is irrelevant because user cannot find files they cannot read
                    # but here for documentation purposes, in case that rule is relaxed
                    pass
                    # wheres.append('OR "_read users".value = $client OR "_read users".value = \'*\'')
            
        tables = " JOIN ".join(tables)
        tables += ' LEFT OUTER JOIN "_read users" ON (files.name = "_read users".file)'

        # custom DEI hack
        tables += ' LEFT OUTER JOIN "_Image Set" ON (files.name = "_Image Set".file)'

        wheres.append(readclauses)
        values["client"] = self.user()
        wheres = " AND ".join([ "(%s)" % where for where in wheres])
        if wheres:
            wheres = "WHERE " + wheres

        query = 'SELECT files.name AS file, files.local AS local, _owner.value AS owner, "_Image Set".file AS imgset FROM %s %s GROUP BY files.name, files.local, owner, imgset' % (tables, wheres)

        if len(excepttables) > 2:
            excepttables.append('"_read users" ON (_owner.file = "_read users".file)')

            # custom DEI hack
            excepttables.append('"_Image Set" ON (files.name = "_Image Set".file)')

            excepttables = " LEFT OUTER JOIN ".join(excepttables)
            exceptwheres = " AND ".join(["(%s)" % where for where in exceptwheres])
            if exceptwheres:
                exceptwheres = "WHERE " + exceptwheres
            query2 = 'SELECT _owner.file AS file, files.local AS local, _owner.value AS owner, "_Image Set".file AS imgset FROM %s %s GROUP BY files.name, files.local, owner, imgset' % (excepttables, exceptwheres)
            query = '(%s) EXCEPT (%s)' % (query, query2)

        query += " ORDER BY file"
        
        #web.debug(query)
        return self.db.query(query, vars=values)

    def select_next_transmit_number(self):
        query = "SELECT NEXTVAL ('transmitnumber')"
        result = self.db.query(query)
        return str(result[0].nextval).rjust(9, '0')

