import urllib
import web
import psycopg2
import os

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
    __slots__ = [ 'dbnstr', 'dbstr', 'db', 'home', 'store_path', 'chunkbytes', 'render', 'typenames' ]

    def __init__(self):
        "store common configuration data for all service classes"
        global render

        myAppName = os.path.basename(web.ctx.env['SCRIPT_NAME'])

        def getParam(suffix):
            return web.ctx.env['%s.%s' % (myAppName, suffix)]

        self.dbnstr = getParam('dbnstr')
        self.dbstr = getParam('dbstr')
        self.home = getParam('home')
        self.store_path = getParam('store_path')
        self.template_path = getParam('template_path')
        self.chunkbytes = int(getParam('chunkbytes'))

        self.render = web.template.render(self.template_path)
        render = self.render # HACK: make this available to exception classes too

        # TODO: pull this from database?
        self.typenames = { '' : 'No content', 'int8' : 'Integer', 'float8' : 'Floating point',
                           'date' : 'Date', 'timestamptz' : 'Date and time with timezone',
                           'text' : 'Text' }

        self.ops = [ ('', 'Exists (ignores value)'),
                     (':not:', 'Does not exists'),
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

    def renderlist(self, title, renderlist):
        return "".join([unicode(r) for r in 
                        [self.render.Top(self.home + web.ctx.homepath, title)] + renderlist + [self.render.Bottom()]])

    def dbtransact(self, body, postCommit):
        """re-usable transaction pattern

           using caller-provided thunks under boilerplate
           commit/rollback/retry logic
        """
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
                raise te
            except (psycopg2.DataError, psycopg2.ProgrammingError), te:
                t.rollback()
                raise BadRequest(data='Logical error: ' + str(te))
            except TypeError, te:
                t.rollback()
                web.debug(te)
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

    def owner(self):
        try:
            results = self.select_file_tag('owner')
            if len(results) > 0:
                return results[0].value
            else:
                return None
        except:
            return None

    def user(self):
        try:
            user = web.ctx.env['REMOTE_USER']
        except:
            return None
        return user

    def userAccess(self, tag, owner, file):
        user = self.user()
        if user:
            if user != owner:
                try:
                    results = self.select_user_restrictions(tag, user, file)
                    if len(results) == 0:
                        return False
                    else:
                        return True
                except:
                    return False
            else:
                return True
        else:
            return False

    def fileAccess(self, tag, user, owner):
        try:
            results = self.select_file_tag_restrictions(tag, user)
            if len(results) == 0 and user != owner:
                return False
            else:
                return True
        except:
            return user == owner

    def tagAccess(self, tag, user, tag_writer):
        """ The tag must have 'users' access or the user must be in the 'writers' list """ 
        if tag_writer == 'users':
            return True
        elif tag_writer != 'writers':
            return False
        try:
            results = self.select_file_tag_restrictions(tag, user)
            if len(results) == 0:
                return False
            else:
                return True
        except:
            return False

    def enforceFileRestriction(self, tag):
        owner = self.owner()
        user = self.user()
        if owner:
            if user:
                if user != owner:
                    if not self.fileAccess(tag, user, owner):
                        raise Forbidden(data="access to dataset %s" % self.data_id)
            else:
                raise Unauthorized(data="access to dataset %s" % self.data_id)
        else:
            pass

    def enforceFileTagRestriction(self, tag_id, policy_tag='write users'):
        results = self.select_file()
        if len(results) == 0:
            raise NotFound(data="dataset %s" % self.data_id)
        results = self.select_tagdef(tag_id)
        if len(results) == 0:
            raise BadRequest(data="The tag %s is not defined on this server." % tag_id)
        tag_writer = results[0].writers
        if tag_writer != 'users':
            owner = self.owner()
            user = self.user()
            if owner:
                if user:
                    if user == owner:
                        pass
                    elif not self.tagAccess(policy_tag, user, tag_writer):
                        raise Forbidden(data="access to tag %s on dataset %s" % (tag_id, self.data_id))
                    else:
                        pass
                else:
                    raise Unauthorized(data="access to tag %s on dataset %s" % (tag_id, self.data_id))
            else:
                pass

    def enforceTagRestriction(self, tag_id):
        results = self.select_tagdef(tag_id)
        if len(results) == 0:
            raise NotFound()
        result = results[0]
        writers = result.writers
        owner = result.owner
        user = self.user()
        if owner:
            if user:
                if user == owner:
                    pass
                elif not self.tagAccess(tag_id, user, writers):
                    raise Forbidden(data="access to tag definition %s" % tag_id)
                else:
                    pass
            else:
                raise Unauthorized(data="access to tag definition %s" % tag_id)
        else:
            raise Forbidden(data="access to tag definition %s" % tag_id)

    def fileTagAccess(self, tag_id):
        try:
            self.enforceFileTagRestriction(tag_id)
            if tag_id in self.ownerTags and self.owner() != self.user():
                return False
        except:
            return False
        return True
      
    def wraptag(self, tagname):
        return '_' + tagname.replace('"','""')

    def gettagvals(self, tagname, data_id=None):
        results = self.select_file_tag(tagname, data_id=data_id)
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

    def select_file(self):
        results = self.db.select('files', where="name = $name", vars=dict(name=self.data_id))
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

    def select_tagdef(self, tagname):
        return self.db.select('tagdefs', where="tagname = $tagname",
                              vars=dict(tagname=tagname))

    def select_tagdefs(self):
        return self.db.select('tagdefs', order="tagname")

    def select_defined_tags(self, where):
        if where:
            return self.db.select('tagdefs', where=where, order="tagname")
        else:
            return self.db.select('tagdefs', order="tagname")

    def insert_tagdef(self):
        self.db.query("INSERT INTO tagdefs ( tagname, typestr, writers, multivalue, owner ) VALUES ( $tag_id, $typestr, $writers, $multivalue, $owner )",
                      vars=dict(tag_id=self.tag_id, typestr=self.typestr, writers=self.writers, multivalue=self.multivalue, owner=self.user()))

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


    def select_file_tag(self, tagname, value=None, data_id=None):
        query = "SELECT * FROM \"%s\"" % (self.wraptag(tagname)) \
                + " WHERE file = $file"
        if value == '':
            query += " AND value IS NULL ORDER BY VALUE"
        elif value:
            query += " AND value = $value ORDER BY VALUE"
        #web.debug(query)
        if data_id == None:
            data_id = self.data_id
        return self.db.query(query, vars=dict(file=data_id, value=value))

    def select_file_tag_restrictions(self, tagname, user):
        query = "SELECT * FROM \"%s\"" % (self.wraptag(tagname)) \
                + " WHERE file = $file AND (value = $value OR value = $any)"
        #web.debug(query)
        return self.db.query(query, vars=dict(file=self.data_id, value=user, any="*"))

    def select_user_restrictions(self, tagname, user, file):
        query = "SELECT * FROM \"%s\"" % (self.wraptag(tagname)) \
                + " WHERE file = $file AND (value = $value OR value = $any)"
        #web.debug(query)
        return self.db.query(query, vars=dict(file=file, value=user, any="*"))

    def select_users_access(self, tagname, file):
        query = "SELECT value FROM \"%s\"" % (self.wraptag(tagname)) \
                + " WHERE file = $file"
        #web.debug(query)
        return self.db.query(query, vars=dict(file=file))

    def select_file_tags(self, tagname=''):
        if tagname:
            where = " AND tagname = $tagname"
        else:
            where = ""
        query = "SELECT tagname FROM filetags WHERE file = $file" \
                + where \
                + " GROUP BY tagname ORDER BY tagname"
        #web.debug(query)
        return self.db.query(query,
                             vars=dict(file=self.data_id, tagname=tagname))

    def select_defined_file_tags(self, where):
        if self.data_id:
            wheres = "WHERE file = $file"
            if where:
                wheres += " AND" + where
        else:
            if where:
                wheres = "WHERE" + where
            else:
                wheres = ""
        query = "SELECT file, tagname FROM filetags join tagdefs using (tagname) " + wheres \
                + " GROUP BY file, tagname ORDER BY file, tagname"
        #web.debug(query)
        return self.db.query(query,
                             vars=dict(file=self.data_id))

    def delete_file_tag(self, tagname, value=None):
        if value == '':
            whereval = " AND value IS NULL"
        elif value:
            whereval = " AND value = $value"
        else:
            whereval = ""
        self.db.query("DELETE FROM \"%s\"" % (self.wraptag(tagname))
                      + " WHERE file = $file" + whereval,
                      vars=dict(file=self.data_id, value=value))
        results = self.select_file_tag(tagname)
        if len(results) == 0:
            # there may be other values tagged still
            self.db.delete("filetags", where="file = $file AND tagname = $tagname",
                           vars=dict(file=self.data_id, tagname=tagname))

    def set_file_tag(self, tagname, value):
        try:
            results = self.select_tagdef(tagname)
            result = results[0]
            tagtype = result.typestr
            multivalue = result.multivalue
        except:
            raise BadRequest(data="The tag %s is not defined on this server." % tag_id)

        if not multivalue:
            results = self.select_file_tag(tagname)
            if len(results) > 0:
                # drop existing value so we can reinsert one standard way
                self.delete_file_tag(tagname)
        else:
            results = self.select_file_tag(tagname, value)
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
        self.db.query(query, vars=dict(file=self.data_id, value=value))
        
        results = self.select_file_tags(tagname)
        if len(results) == 0:
            self.db.query("INSERT INTO filetags (file, tagname) VALUES ($file, $tagname)",
                          vars=dict(file=self.data_id, tagname=tagname))
        else:
            # may already be reverse-indexed in multivalue case
            pass            

    def select_files_by_predlist(self):

        for pred in self.predlist:
            results = self.select_tagdef(pred['tag'])
            if len(results) == 0:
                raise BadRequest(data="The tag %s is not defined on this server." % pred['tag'])

        tables = ['_owner']
        excepttables = ['_owner']
        wheres = []
        values = dict()

        for p in range(0, len(self.predlist)):
            pred = self.predlist[p]
            tag = pred['tag']
            op = pred['op']
            vals = pred['vals']
            if op == ':not:':
                excepttables.append("\"%s\" USING (file)" % self.wraptag(tag))
            else:
                tables.append("\"%s\" AS t%s USING (file)" % (self.wraptag(tag), p))
                if op and vals and len(vals) > 0:
                    valpreds = []
                    for v in range(0, len(vals)):
                        valpreds.append("t%s.value %s $val%s_%s" % (p, self.opsDB[op], p, v))
                        values["val%s_%s" % (p, v)] = vals[v]
                    wheres.append(" OR ".join(valpreds))
            
        tables = " JOIN ".join(tables)
        tables += ' LEFT OUTER JOIN "_read users" USING (file)'
        wheres.append('_owner.value = $client OR "_read users".value = $client OR "_read users".value = \'*\'')
        values["client"] = self.user()
        wheres = " AND ".join([ "(%s)" % where for where in wheres])
        if wheres:
            wheres = "WHERE " + wheres

        query = 'SELECT file, _owner.value AS owner FROM %s %s GROUP BY file, owner' % (tables, wheres)

        if len(excepttables) > 1:
            excepttables = " JOIN ".join(excepttables)
            query2 = 'SELECT file, _owner.value AS owner FROM %s GROUP BY file, owner' % excepttables
            query = '(%s) EXCEPT (%s)' % (query, query2)

        query += " ORDER BY file"
        
        #web.debug(query)
        return self.db.query(query, vars=values)

