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

def urlquote(url):
    "define common URL quote mechanism for registry URL value embeddings"
    return urllib.quote(url, safe="")

class NotFound (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        web.HTTPError.__init__(self, '404 Not Found', headers=headers, data=data)

class Forbidden (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        web.HTTPError.__init__(self, '403 Forbidden', headers=headers, data=data)

class Unauthorized (web.HTTPError):
    "provide an exception we can catch in our own transactions"
    def __init__(self, data='', headers={}):
        web.HTTPError.__init__(self, '401 Unauthorized', headers=headers, data=data)

class Application:
    "common parent class of all service handler classes to use db etc."
    __slots__ = [ 'dbnstr', 'dbstr', 'db', 'home', 'store_path', 'chunkbytes', 'render', 'typenames' ]

    def __init__(self):
        "store common configuration data for all service classes"

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

        # TODO: pull this from database?
        self.typenames = { '' : 'No content', 'int8' : 'Integer', 'float8' : 'Floating point', 
                           'date' : 'Date', 'timestamptz' : 'Date and time with timezone',
                           'text' : 'Text' }

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
            except Forbidden, te:
                t.rollback()
                raise te
            except Unauthorized, te:
                t.rollback()
                raise te
            except TypeError, te:
                t.rollback()
                raise NotFound()
            except NotFound, nf:
                t.rollback()
                raise NotFound()
            except psycopg2.IntegrityError, e:
                t.rollback()
                if count > limit:
                    raise web.BadRequest()
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

    def restrictedFile(self):
        try:
            results = self.select_file_tag('restricted')
            if len(results) > 0:
                return True
        except:
            pass
        return False

    def enforceFileRestriction(self):
        if self.restrictedFile():
            owner = self.owner()
            user = self.user()
            if owner:
                if user:
                    if user != owner:
                        raise Forbidden(data="Access to %s forbidden." % self.data_id)
                    else:
                        pass
                else:
                    raise Unauthorized(data="Access to %s requires authorization." % self.data_id)
            else:
                pass

    def enforceFileTagRestriction(self, tag_id):
        results = self.select_tagdef(tag_id)
        if results[0].restricted:
            owner = self.owner()
            user = self.user()
            if owner:
                if user:
                    if user != owner:
                        raise web.Forbidden()
                    else:
                        pass
                else:
                    raise web.Unauthorized()
            else:
                pass

    def isFileTagRestricted(self, tag_id):
        try:
            self.enforceFileTagRestriction(tag_id)
        except:
            return True
        return False
      
    def wraptag(self, tagname):
        return '_' + tagname.replace('"','""')

    def tagval(self, tagname):
        results = self.select_file_tag(tagname)
        try:
            value = results[0].value
        except:
            value = None
        return value

    def select_file(self):
        results = self.db.select('files', where="name = $name", vars=dict(name=self.data_id))
        return results

    def select_files(self):
        results = self.db.select('files', order='name')
        return results

    def insert_file(self):
        self.db.query("INSERT INTO files VALUES ( $name, $local, $location )",
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

    def insert_tagdef(self):
        self.db.query("INSERT INTO tagdefs ( tagname, typestr, restricted ) VALUES ( $tag_id, $typestr, $restricted )",
                      vars=dict(tag_id=self.tag_id, typestr=self.typestr, restricted=self.restricted))

        tabledef = "CREATE TABLE \"%s\"" % (self.wraptag(self.tag_id))
        tabledef += " ( file text REFERENCES files (name) ON DELETE CASCADE"
        if self.typestr != '':
            tabledef += ", value %s" % (self.typestr)
        tabledef += ", UNIQUE(file) )"
        self.db.query(tabledef)
        return True

    def delete_tagdef(self):
        self.db.query("DELETE FROM tagdefs WHERE tagname = $tag_id",
                      vars=dict(tag_id=self.tag_id))
        self.db.query("DROP TABLE \"%s\"" % (self.wraptag(self.tag_id)))


    def select_file_tag(self, tagname):
        return self.db.query("SELECT * FROM \"%s\"" % (self.wraptag(tagname))
                             + " WHERE file = $file", vars=dict(file=self.data_id))

    def select_file_tags(self):
        return self.db.query("SELECT tagname FROM filetags WHERE file = $file ORDER BY tagname",
                             vars=dict(file=self.data_id))

    def delete_file_tag(self, tagname):
        self.db.query("DELETE FROM \"%s\"" % (self.wraptag(tagname)) + " WHERE file = $file",
                      vars=dict(file=self.data_id))
        self.db.delete("filetags", where="file = $file AND tagname = $tagname",
                       vars=dict(file=self.data_id, tagname=tagname))

    def set_file_tag(self, tagname, value):
        try:
            results = self.select_tagdef(tagname)
            tagtype = results[0].typestr
        except:
            raise web.BadRequest()

        results = self.select_file_tag(tagname)
        if len(results) > 0:
            # drop existing value so we can reinsert one standard way
            self.delete_file_tag(tagname)

        if value != '' and tagtype != '':
            self.db.query("INSERT INTO \"%s\"" % (self.wraptag(tagname))
                          + " ( file, value ) VALUES ( $file, $value )",
                          vars=dict(file=self.data_id, value=value))
        else:
            # insert untyped or typed w/ default value...
            self.db.query("INSERT INTO \"%s\"" % (self.wraptag(tagname))
                          + " ( file ) VALUES ( $file )",
                          vars=dict(file=self.data_id))

        self.db.query("INSERT INTO filetags (file, tagname) VALUES ($file, $tagname)",
                      vars=dict(file=self.data_id, tagname=tagname))

    def select_files_having_tagnames(self):
        for t in self.tagnames:
            try:
                self.select_tagdef(t)[0]
            except:
                raise web.BadRequest()

        tags = [ t for t in self.tagnames ]

        if len(self.tagnames) > 1:
            tables = " JOIN ".join(["\"%s\"" % (self.wraptag(tags[0])),
                                    " JOIN ".join([ "\"%s\" USING (file)" % (self.wraptag(t))
                                                    for t in tags[1:] ])])
        else:
            tables = "\"%s\"" % (self.wraptag(tags[0]))
        return self.db.query("SELECT file FROM %s ORDER BY file" % (tables))

