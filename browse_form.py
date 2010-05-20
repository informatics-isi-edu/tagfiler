import os
import web

from dataserv_app import Application, NotFound, urlquote

class FormIO (Application):
    """Basic file upload forms"""
    __slots__ = [ ]

    def __init__(self):
        Application.__init__(self)

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

class FileList (Application):
    """Basic dataset listing"""
    __slots__ = []

    def __init__(self):
        Application.__init__(self)

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

class FileVersionList (Application):
    """Basic dataset history listing"""
    __slots__ = []

    def __init__(self):
        Application.__init__(self)

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


class TagForm (Application):
    __slots__ = [ 'target' ]
    def __init__(self):
        Application.__init__(self)
        self.target = self.home + web.ctx.homepath + '/tagdef'

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

    def POST(self, uri):

        storage = web.input()
        try:
            self.tag_id = storage.tag
            self.typestr = storage.type
        except:
            raise web.BadRequest()

        def body():
            self.insert_tagdef()
            return [ ( tagdef.tagname, tagdef.typestr) for tagdef in self.select_tagdefs() ]

        def postCommit(tagdefs):
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting(self.target, tagdefs, self.typenames),
                                    self.render.TagdefNew(self.target, tagdefs, self.typenames)])

        return self.dbtransact(body, postCommit)


class FileTags (Application):
    __slots__ = []

    def __init__(self):
        Application.__init__(self)

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
            return value

        return self.dbtransact(body, postCommit)

    def browseBody(self):
        tagdefs = [ tagdef for tagdef in self.select_tagdefs() ]
        tags = [ result.tagname for result in self.select_file_tags() ]
        tagvals = [ (tag, self.tagval(tag)) for tag in tags ]
        return (tagvals, tagdefs)

    def browsePostCommit(self, results):
        tagvals, tagdefs = results
        target = self.home + web.ctx.homepath + '/tags/' + urlquote(self.data_id)
        if len(tagvals) > 0:
            return self.renderlist("\"%s\" tags" % (self.data_id),
                                   [self.render.FileTagExisting(target, tagvals),
                                    self.render.FileTagNew(target, tagdefs)])
        else:
            return self.renderlist("\"%s\" tags" % (self.data_id),
                                   [self.render.FileTagNew(target, tagdefs)])

    def GETall(self, uri):
        # HTML get of all tags on one file...
        def body():
            return self.browseBody()

        def postCommit(results):
            return self.browsePostCommit(results)
            
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

    def deletetag(self):
        # internal helper
        def body():
            self.delete_file_tag(self.tag_id)
            return ''
        def postCommit(results):
            return results
        return self.dbtransact(body, postCommit)
        
    def DELETE(self, uri):
        # RESTful delete of exactly one tag on one file...
        if self.tag_id == '' or self.value != '':
            raise web.BadRequest
        return self.deletetag()

    def POST(self, uri):
        # simulate RESTful actions and provide helpful web pages to browsers
        def putBody():
            self.set_file_tag(self.tag_id, self.value)
            return self.browseBody()

        def deleteBody():
            self.deletetag()
            return self.browseBody()

        def postCommit(results):
            return self.browsePostCommit(results)

        storage = web.input()
        try:
            action = storage.action
            self.tag_id = storage.tag

            if action == 'put':
                try:
                    self.value = storage.value
                except:
                    self.value = ''

                return self.dbtransact(putBody, postCommit)
            elif action == 'delete':
                return self.dbtransact(deleteBody, postCommit)
            else:
                raise web.BadRequest()
        except:
            raise web.BadRequest()

class HasTags (Application):
    __slots__ = [ 'action' ]

    def __init__(self):
        Application.__init__(self)
        self.action = 'query'

    def qtarget(self):
        return self.home + web.ctx.homepath + '/query/' + ';'.join([t for t in self.tagnames])

    def GET(self, uri):

        # this interface has both REST and form-based functions
        tagname = None
        try:
            tagname = self.queryopts['tag']
            self.action = self.queryopts['action']
        except:
            pass

        if self.action == 'add':
            self.tagnames = self.tagnames | set([tagname])
        elif self.action == 'delete':
            self.tagnames = self.tagnames - set([tagname])
        elif self.action == 'query':
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
            return 

        # this only runs if we need to do a DB query
        return self.dbtransact(body, postCommit)


            
