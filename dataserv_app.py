import urllib
import web
import psycopg2

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
        web.HTTPError.__init__(self, 404, headers=headers, data=data)

class Application:
    "common parent class of all service handler classes to use db etc."
    __slots__ = [ 'dbnstr', 'dbstr', 'db', 'home', 'store_path', 'chunkbytes', 'render', 'typenames' ]

    def __init__(self):
        "store common configuration data for all service classes"

        self.dbnstr = web.ctx.env['dataserv.dbnstr']
        self.dbstr = web.ctx.env['dataserv.dbstr']
        self.home = web.ctx.env['dataserv.home']
        self.store_path = web.ctx.env['dataserv.store_path']
        self.template_path = web.ctx.env['dataserv.template_path']
        self.chunkbytes = int(web.ctx.env['dataserv.chunkbytes'])

        self.render = web.template.render(self.template_path)

        # TODO: pull this from database?
        self.typenames = { '' : 'No content', 'int8' : 'Integer', 'float8' : 'Floating point', 
                           'date' : 'Date', 'timestamptz' : 'Date and time with timezone',
                           'text' : 'Text' }

    def renderlist(self, title, renderlist):
        return "".join([unicode(r) for r in 
                        [self.render.Top(title)] + renderlist + [self.render.Bottom()]])

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
            except TypeError as te:
                t.rollback()
                return web.notfound()
            except NotFound as nf:
                t.rollback()
                return web.notfound(nf.data)
            except psycopg2.IntegrityError as e:
                t.rollback()
                if count > limit:
                    raise web.BadRequest()
                # else fall through to retry...
            except:
                t.rollback()
                raise
        return postCommit(bodyval)

    # a bunch of little database access helpers for this app, to be run inside
    # the dbtransact driver

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
        return results[0]

    def insert_file(self):
        self.db.query("INSERT INTO files ( name ) VALUES ( $name )",
                      vars=dict(name=self.data_id))

    def select_file_version_max(self):
        results = self.db.query("SELECT max(version) AS max_version "
                                + "FROM fileversions WHERE name = $name",
                                vars=dict(name=self.data_id))
        return results[0].max_version

    def select_file_version(self):
        return self.db.select('fileversions', where="name = $name AND version = $version",
                              vars=dict(name=self.data_id, version=self.vers_id))

    def delete_file_version(self):
        self.db.delete('fileversions', where="name=$name AND version = $version",
                       vars=dict(name=self.data_id, version=vers_id))

    def insert_file_version(self):
        try:
            self.select_file()
        except:
            self.insert_file()
        self.db.query("INSERT INTO fileversions ( name, version ) VALUES ( $name, $version )",
                      vars=dict(name=self.data_id, version=self.vers_id))

    def select_files_versions_max(self):
        return self.db.query("SELECT name, max(version) AS version FROM fileversions GROUP BY name")

    def select_file_versions(self):
        return self.db.query("SELECT version FROM fileversions"
                             + " WHERE name = $name ORDER BY version",
                             vars=dict(name=self.data_id))

    def select_tagdef(self, tagname):
        return self.db.select('tagdefs', where="tagname = $tagname",
                              vars=dict(tagname=tagname))

    def select_tagdefs(self):
        return self.db.select('tagdefs')

    def insert_tagdef(self):
        self.db.query("INSERT INTO tagdefs ( tagname, typestr ) VALUES ( $tag_id, $typestr )",
                      vars=dict(tag_id=self.tag_id, typestr=self.typestr))

        tabledef = "CREATE TABLE \"%s\"" % (self.wraptag(self.tag_id))
        tabledef += " ( file text REFERENCES files (name) ON DELETE CASCADE"
        if self.typestr != '':
            tabledef += ", value %s" % (self.typestr)
        tabledef += ", UNIQUE(file) )"
        web.debug(tabledef)
        self.db.query(tabledef)
        return True

    def select_file_tag(self, tagname):
        return self.db.query("SELECT * FROM \"%s\"" % (self.wraptag(tagname))
                             + " WHERE file = $file", vars=dict(file=self.data_id))

    def select_file_tags(self):
        return self.db.query("SELECT tagname FROM filetags WHERE file = $file",
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
                self.select_tagdef(t)
            except:
                raise web.BadRequest()

        tags = [ t for t in self.tagnames ]

        if len(self.tagnames) > 1:
            tables = " JOIN ".join(["\"%s\"" % (self.wraptag(tags[0])),
                                    " JOIN ".join([ "\"%s\" USING (file)" % (self.wraptag(t))
                                                    for t in tags[1:] ])])
        else:
            tables = "\"%s\"" % (self.wraptag(tags[0]))

        return self.db.query("SELECT file FROM %s" % (tables))

