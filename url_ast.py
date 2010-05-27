# define abstract syntax tree nodes for more readable code

import web
import urllib
from dataserv_app import Application, NotFound, urlquote
from rest_fileio import FileIO

class Node (object, Application):
    """Abstract AST node for all URI patterns"""

    __slots__ = [ 'appname' ]

    def __init__(self, appname):
        self.appname = appname
        Application.__init__(self)

class FileList (Node):
    """Represents a bare FILE/ URI which means give a listing of all files"""

    __slots__ = []

    def __init__(self, appname):
        Node.__init__(self, appname)

    def GET(self, uri):
        
        web.header('Content-Type', 'text/html;charset=ISO-8859-1')

        def body():
            return self.select_files_versions_max()

        def postCommit(results):
            target = self.home + web.ctx.homepath
            files = [ result.name for result in results ]
            if len(files) > 0:
                return self.renderlist("Repository Summary",
                                       [self.render.Commands(target),
                                        self.render.FileList(target, files, urlquote)])
            else:
                return self.renderlist("Repository Summary",
                                       [self.render.Commands(target)])

        return self.dbtransact(body, postCommit)

class FileHistory (Node):
    """Represents a VERSION/data_id URI which means give a listing of revisions for the file"""

    __slots__ = [ 'data_id']

    def __init__(self, appname, data_id):
        Node.__init__(self, appname)
        self.data_id = data_id

    def GET(self, uri):
        
        web.header('Content-Type', 'text/html;charset=ISO-8859-1')

        def body():
            return self.select_file_versions()

        def postCommit(results):
            target = self.home + web.ctx.homepath
            vers = [ result.version for result in results ]
            return self.renderlist("\"%s\" history" % (self.data_id),
                                   [self.render.FileVersionList(target, self.data_id, vers, urlquote)])

        return self.dbtransact(body, postCommit)

class FileIdVersion (Node, FileIO):
    """Represents a direct FILE/data_id/vers_id URI

       Just creates filename and lets FileIO do the work.

    """
    __slots__ = [ 'data_id', 'vers_id' ]
    def __init__(self, appname, data_id, vers_id=None):
        Node.__init__(self, appname)
        self.data_id = data_id
        self.vers_id = vers_id

    def makeFilename(self):
        return "%s/%s/%s" % (self.store_path, self.data_id, self.vers_id)

class Upload (Node):
    """Represents UPLOAD/ and UPLOAD/data_id URIs"""

    __slots__ = [ 'data_id' ]

    def __init__(self, appname, data_id=None):
        Node.__init__(self, appname)
        self.data_id = data_id

    def GET(self, uri):
        """send form to client"""

        web.header('Content-Type', 'text/html;charset=ISO-8859-1')

        if self.data_id == None:
            target = self.home + web.ctx.homepath + '/upload'
            return self.renderlist("Prepare to upload",
                                   [self.render.NameForm(target)])
        else:
            # getting a FileForm guides browser to upload file
            target = self.home + web.ctx.homepath + '/file/' + urlquote(self.data_id)
            return self.renderlist("Upload data file",
                                   [self.render.FileForm(target)])

    def POST(self, uri):
        """process form submission from client"""

        if self.data_id != None:
            raise web.BadRequest()

        # post form data comes from HTTP header, not URI
        storage = web.input()
        self.data_id = storage.name

        if self.data_id == None:
            raise web.BadRequest()

        # posting a NameForm gets a FileForm:
        #    POST app / upload
        #      with  name = foo
        #    GET  app / upload / name
        # these are equivalent functions, one REST, one for browser
        return self.GET(uri + '/' + urlquote(self.data_id))

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

    __slots__ = [ 'tag_id', 'typestr', 'target', 'action', 'tagdefs' ]

    def __init__(self, appname, tag_id=None, typestr=None):
        Node.__init__(self, appname)
        self.tag_id = tag_id
        self.typestr = typestr
        self.target = self.home + web.ctx.homepath + '/tagdef'
        self.action = None
        self.tagdefs = {}

    def GET(self, uri):

        if self.tag_id != None or self.typestr != None:
            raise web.BadRequest()

        web.header('Content-Type', 'text/html;charset=ISO-8859-1')

        def body():
            return [ ( tagdef.tagname, tagdef.typestr) for tagdef in self.select_tagdefs() ]

        def postCommit(tagdefs):
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting(self.target, tagdefs, self.typenames),
                                    self.render.TagdefNew(self.target, tagdefs, self.typenames)])

        return self.dbtransact(body, postCommit)

    def DELETE(self, uri):
        
        def body():
            self.delete_tagdef()
            return ''

        def postCommit(results):
            return ''

        return self.dbtransact(body, postCommit)
                
    def POST(self, uri):

        storage = web.input()
        try:
            self.action = storage.action
            for key in storage.keys():
                if key[0:4] == 'tag-':
                    if storage[key] != '':
                        typestr = storage['type-%s' % (key[4:])]
                        self.tagdefs[storage[key]] = typestr
            try:
                self.tag_id = storage.tag
            except:
                pass
            
        except:
            raise web.BadRequest()

        def body():
            if self.action == 'add':
                for tagname in self.tagdefs.keys():
                    self.tag_id = tagname
                    self.typestr = self.tagdefs[tagname]
                    self.insert_tagdef()
            elif self.action == 'delete':
                self.delete_tagdef()
            else:
                raise web.BadRequest()
            return None

        def postCommit(results):
            # send client back to get form page again
            raise web.seeother('/tagdef')

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/data_id URIs"""

    __slots__ = [ 'data_id', 'tag_id', 'value', 'tagvals' ]

    def __init__(self, appname, data_id, tag_id='', value=''):
        Node.__init__(self, appname)
        self.data_id = data_id
        self.tag_id = tag_id
        self.value = value
        self.tagvals = {}

    def GETtag(self, uri):
        # RESTful get of exactly one tag on one file...
        def body():
            try:
                results = self.select_file_tag(self.tag_id)
                res = results[0]
                try:
                    value = res.value
                except:
                    value = ''
            except:
                raise NotFound()
            return value

        def postCommit(value):
            # return raw value to REST client
            # BUG?  will this ever be a non-string result?
            return value

        return self.dbtransact(body, postCommit)

    def GETall(self, uri):
        # HTML get of all tags on one file...
        def body():
            tagdefs = [ tagdef for tagdef in self.select_tagdefs() ]
            tags = [ result.tagname for result in self.select_file_tags() ]
            tagvals = [ (tag, self.tagval(tag)) for tag in tags ]
            return (tagvals, tagdefs)

        def postCommit(results):
            tagvals, tagdefs = results
            apptarget = self.home + web.ctx.homepath
            return self.renderlist("\"%s\" tags" % (self.data_id),
                                   [self.render.FileTagExisting(apptarget, self.data_id, tagvals, urlquote),
                                    self.render.FileTagNew(apptarget, self.data_id, tagdefs, self.typenames, urlquote)])
            
        return self.dbtransact(body, postCommit)

    def GET(self, uri=None):
        # dispatch variants, browsing and REST
        if self.tag_id != '':
            return self.GETtag(uri)
        else:
            return self.GETall(uri)

    def PUT(self, uri):
        # RESTful put of exactly one tag on one file...
        if self.tag_id == '':
            raise web.BadRequest()
        self.value = web.ctx.env['wsgi.input'].read()

        def body():
            self.set_file_tag(self.tag_id, self.value)
            return None

        def postCommit(results):
            return ''
            
        return self.dbtransact(body, postCommit)

    def DELETE(self, uri):
        # RESTful delete of exactly one tag on one file...
        if self.tag_id == '' or self.value != '':
            raise web.BadRequest

        def body():
            self.delete_file_tag(self.tag_id)
            return None

        def postCommit(results):
            return ''

        return self.dbtransact(body, postCommit)

    def POST(self, uri):
        # simulate RESTful actions and provide helpful web pages to browsers
        def nullBody():
            return None

        def putBody():
            for tag_id in self.tagvals:
                self.set_file_tag(tag_id, self.tagvals[tag_id])
            return None

        def deleteBody():
            self.delete_file_tag(self.tag_id)
            return None

        def postCommit(results):
            url = '/tags/' + urlquote(self.data_id)
            raise web.seeother(url)

        storage = web.input()
        try:
            action = storage.action
            for key in storage.keys():
                if key[0:4] == 'set-':
                    tag_id = key[4:]
                    try:
                        value = storage['val-%s' % (tag_id)]
                    except:
                        value = ''
                    self.tagvals[urllib.unquote(tag_id)] = value
            try:
                self.tag_id = storage.tag
            except:
                pass
        except:
            raise web.BadRequest()

        if action == 'put':
            if len(self.tagvals) > 0:
                web.debug(self.tagvals)
                return self.dbtransact(putBody, postCommit)
            else:
                return self.dbtransact(nullBody, postCommit)
        elif action == 'delete':
            return self.dbtransact(deleteBody, postCommit)
        else:
            raise web.BadRequest()

class Query (Node):
    __slots__ = [ 'tagnames', 'queryopts', 'action' ]
    def __init__(self, appname, tagnames=[], queryopts={}):
        Node.__init__(self, appname)
        self.tagnames = set(tagnames)
        self.queryopts = queryopts
        self.action = 'query'

    def qtarget(self):
        return self.home + web.ctx.homepath + '/query/' + ';'.join([urlquote(t) for t in self.tagnames])

    def GET(self, uri):
        # this interface has both REST and form-based functions
        tagname = None
        try:
            self.action = self.queryopts['action']
            tagname = self.queryopts['tag']
        except:
            pass

        if self.action == 'add':
            self.tagnames = self.tagnames | set([tagname])
        elif self.action == 'delete':
            self.tagnames = self.tagnames - set([tagname])
        elif self.action == 'query':
            pass
        elif self.action == 'edit':
            pass
        else:
            raise web.BadRequest()

        def body():
            if len(self.tagnames) > 0:
                files = [ res.file for res in self.select_files_having_tagnames() ]
            else:
                files = []
            alltags = [ tagdef.tagname for tagdef in self.select_tagdefs() ]
            return ( files, alltags )

        def postCommit(results):
            files, alltags = results

            target = self.home + web.ctx.homepath

            if self.action in set(['add', 'delete']):
                raise web.seeother(self.qtarget() + '?action=edit')

            if len(self.tagnames) == 0:
                # render a blank starting form
                return self.renderlist("Query by Tags",
                                       [self.render.QueryAdd(self.qtarget(), alltags)])

            if self.action == 'query':
                return self.renderlist("Query Results",
                                       [self.render.FileList(target, files, urlquote)])
            else:
                return self.renderlist("Query by Tags",
                                       [self.render.QueryAdd(self.qtarget(), alltags),
                                        self.render.QueryView(self.qtarget(), self.tagnames),
                                        self.render.FileList(target, files, urlquote)])

        # this only runs if we need to do a DB query
        return self.dbtransact(body, postCommit)
