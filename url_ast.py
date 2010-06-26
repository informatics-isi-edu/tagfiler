# define abstract syntax tree nodes for more readable code

import web
import urllib
import re
from dataserv_app import Application, NotFound, BadRequest, Conflict, urlquote
from rest_fileio import FileIO

class Node (object, Application):
    """Abstract AST node for all URI patterns"""

    __slots__ = [ 'appname' ]

    def __init__(self, appname):
        self.appname = appname
        Application.__init__(self)

class FileList (Node):
    """Represents a bare FILE/ URI

       GET  FILE  or FILE/         -- gives a listing
       GET  FILE?action=define     -- gives a new NameForm
       POST FILE?name=foo&type=t   -- redirects to GET FILE/name?type=t&action=define
    """

    __slots__ = []

    def __init__(self, appname):
        Node.__init__(self, appname)

    def GET(self, uri):
        
        web.header('Content-Type', 'text/html;charset=ISO-8859-1')

        def body():
            return self.select_files()

        def postCommit(results):
            target = self.home + web.ctx.homepath
            files = [ result.name for result in results ]
            return self.renderlist("Repository Summary",
                                   [self.render.Commands(target),
                                    self.render.FileList(target, files, urlquote)])

        storage = web.input()
        action = None
        try:
            action = storage.action
        except:
            pass

        if action == 'define':
            target = self.home + web.ctx.homepath + '/file'
            return self.renderlist("Define a dataset",
                                   [self.render.NameForm(target)])
        else:
            return self.dbtransact(body, postCommit)

    def POST(self, uri):

        storage = web.input()
        try:
            name = storage.name
            filetype = storage.type
            restricted = storage.restricted
        except:
            raise BadRequest(data="Missing one of the required form fields (name, filetype, restricted).")

        if name == '':
            raise BadRequest(data="The form field name must not be empty.")
        else:
            raise web.seeother(self.home + web.ctx.homepath + '/file/' + urlquote(name)
                               + '?type=' + urlquote(filetype) + '&action=define' + '&restricted=' + urlquote(restricted))
        

class FileId(Node, FileIO):
    """Represents a direct FILE/data_id URI

       Just creates filename and lets FileIO do the work.

    """
    __slots__ = [ 'data_id', 'location', 'local', 'queryopts' ]
    def __init__(self, appname, data_id, location=None, local=False, queryopts={}):
        Node.__init__(self, appname)
        FileIO.__init__(self)
        self.data_id = data_id
        self.location = location
        self.local = local
        self.queryopts = queryopts

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

    __slots__ = [ 'tag_id', 'typestr', 'target', 'action', 'tagdefs', 'restricted', 'multivalue', 'queryopts' ]

    def __init__(self, appname, tag_id=None, typestr=None, queryopts={}):
        Node.__init__(self, appname)
        self.tag_id = tag_id
        self.typestr = typestr
        self.restricted = None
        self.multivalue = None
        self.target = self.home + web.ctx.homepath + '/tagdef'
        self.action = None
        self.tagdefs = {}
        self.queryopts = queryopts

    def GET(self, uri):

        if self.tag_id != None:
            if len(self.queryopts) > 0:
                raise BadRequest(data="Query options are not supported on this interface.")
            else:
                return self.GETone(uri)
        else:
            return self.GETall(uri)

    def GETall(self, uri):

        def body():
            predefined = [ ( tagdef.tagname, tagdef.typestr, tagdef.restricted, tagdef.multivalue)
                     for tagdef in self.select_defined_tags('owner is null') ]
            userdefined = [ ( tagdef.tagname, tagdef.typestr, tagdef.restricted, tagdef.multivalue)
                     for tagdef in self.select_defined_tags('owner is not null') ]
            return (predefined, userdefined)

        def postCommit(tagdefs):
            web.header('Content-Type', 'text/html;charset=ISO-8859-1')
            predefined, userdefined = tagdefs
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting(self.target, predefined, self.typenames, 'System'),
                                    self.render.TagdefExisting(self.target, userdefined, self.typenames, 'User'),
                                    self.render.TagdefNew(self.target, tagdefs, self.typenames)])

        if len(self.queryopts) > 0:
            raise BadRequest(data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)

    def GETone(self,uri):

        def body():
            results = self.select_tagdef(self.tag_id)
            if len(results) == 0:
                raise NotFound(data='tag definition %s' % (self.tag_id))
            return results[0]

        def postCommit(tagdef):
            try:
                web.header('Content-Type', 'application/x-www-form-urlencoded')
                return ('typestr=' + urlquote(tagdef.typestr) 
                        + '&restricted=' + urlquote(unicode(tagdef.restricted))
                        + '&multivalue=' + urlquote(unicode(tagdef.multivalue)))
            except:
                raise NotFound(data='tag definition %s' % (self.tag_id))

        if len(self.queryopts) > 0:
            raise BadRequest(data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)

    def DELETE(self, uri):
        
        def body():
            results = self.select_tagdef(self.tag_id)
            if len(results) == 0:
                raise NotFound(data='tag definition %s' % (self.tag_id))
            self.enforceTagRestriction(self.tag_id)
            self.delete_tagdef()
            return ''

        def postCommit(results):
            return ''

        if len(self.queryopts) > 0:
            raise BadRequest(data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)
                
    def PUT(self, uri):

        if self.tag_id == None:
            raise BadRequest(data="Tag definitions require a non-empty tag name.")

        # self.typestr and self.restricted take precedence over queryopts...

        if self.typestr == None:
            try:
                self.typestr = self.queryopts['typestr']
            except:
                self.typestr = ''

        if self.restricted == None:
            try:
                restricted = self.queryopts['restricted'].lower()
            except:
                restricted = 'false'
            if restricted in [ 'true', 't', 'yes', 'y' ]:
                self.restricted = True
            else:
                self.restricted = False

        if self.multivalue == None:
            try:
                multivalue = self.queryopts['multivalue'].lower()
            except:
                multivalue = 'false'
            if multivalue in [ 'true', 't', 'yes', 'y' ]:
                self.multivalue = True
            else:
                self.multivalue = False

        def body():
            results = self.select_tagdef(self.tag_id)
            if len(results) > 0:
                raise Conflict(data="Tag %s is already defined." % self.tag_id)
            self.insert_tagdef()
            return None

        def postCommit(results):
            # send client back to get new tag definition
            # or should we just return empty success result?
            raise web.seeother('/tagdef/' + urlquote(self.tag_id))

        return self.dbtransact(body, postCommit)

    def POST(self, uri):

        storage = web.input()
        try:
            self.action = storage.action
            for key in storage.keys():
                if key[0:4] == 'tag-':
                    if storage[key] != '':
                        typestr = storage['type-%s' % (key[4:])]
                        restricted = storage['restricted-%s' % (key[4:])]
                        multivalue = storage['multivalue-%s' % (key[4:])]
                        self.tagdefs[storage[key]] = (typestr, restricted, multivalue)
            try:
                self.tag_id = storage.tag
            except:
                pass
            
        except:
            raise BadRequest(data="Error extracting form data.")

        def body():
            if self.action == 'add':
                for tagname in self.tagdefs.keys():
                    self.tag_id = tagname
                    self.typestr, self.restricted, self.multivalue = self.tagdefs[tagname]
                    results = self.select_tagdef(self.tag_id)
                    if len(results) > 0:
                        raise Conflict(data="Tag %s is already defined." % self.tag_id)
                    self.insert_tagdef()
            elif self.action == 'delete' or self.action == 'CancelDelete':
                self.enforceTagRestriction(self.tag_id)
                return None
            elif self.action == 'ConfirmDelete':
                self.enforceTagRestriction(self.tag_id)
                self.delete_tagdef()
            else:
                raise BadRequest(data="Form field action=%s not understood." % self.action)
            return None

        def postCommit(results):
            if self.action == 'delete':
                return self.renderlist("Delete Confirmation",
                                   [self.render.ConfirmForm(self.home + web.ctx.homepath, 'tagdef', self.tag_id, urlquote)])
            else:
                # send client back to get form page again
                raise web.seeother('/tagdef')

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/data_id URIs"""

    __slots__ = [ 'data_id', 'tag_id', 'value', 'tagvals' ]

    def __init__(self, appname, data_id=None, tag_id='', value=None):
        Node.__init__(self, appname)
        self.data_id = data_id
        self.tag_id = tag_id
        self.value = value
        self.tagvals = {}

    def mystr(self, val):
        if type(val) == type(1.0):
            return re.sub("0*e", "0e", "%.48e" % val)
        else:
            return str(val)
            
    def GETtag(self, uri):
        # RESTful get of exactly one tag on one file...
        def body():
            results = self.select_tagdef(self.tag_id)
            if len(results) == 0:
                raise NotFound(data='tag definition %s' % self.tag_id)
            results = self.select_file_tag(self.tag_id, self.value)
            if len(results) == 0:
                if self.value == None:
                    raise NotFound(data='tag %s on dataset %s' % (self.tag_id, self.data_id))
                elif self.value == '':
                    raise NotFound(data='tag %s = "" on dataset %s' % (self.tag_id, self.data_id))
                else:
                    raise NotFound(data='tag %s = %s on dataset %s' % (self.tag_id, self.value, self.data_id))
            values = []
            for res in results:
                try:
                    value = res.value
                    if value == None:
                        value = ''
                    values.append(value)
                except:
                    pass
            return values

        def postCommit(values):
            # return raw value to REST client
            web.header('Content-Type', 'application/x-www-form-urlencoded')

            return "&".join([(urlquote(self.tag_id) + '=' + urlquote(self.mystr(val))) for val in values])

        return self.dbtransact(body, postCommit)

    def GETall(self, uri):
        # HTML get of all tags on one file...
        def listmax(list):
            if len(list) > 0:
                return max(list)
            else:
                return 0
        
        def body():
            def buildtaginfo(where1, where2):
                tagdefs = [ tagdef for tagdef in self.select_defined_tags(where1) ]
                tagdefsdict = dict([ (tagdef.tagname, tagdef) for tagdef in tagdefs ])
                filetags = [ (result.file, result.tagname) for result in self.select_defined_file_tags(where2) ]
                filetagvals = [ (file, tag, [self.mystr(val) for val in self.gettagvals(tag, data_id=file)]) for file, tag in filetags ]
                length = listmax([listmax([ len(val) for val in vals]) for file, tag, vals in filetagvals])
                return ( self.predefinedTags, # excludes
                         tagdefs,
                         tagdefsdict,
                         filetags,
                         filetagvals,
                         length )
            
            return (buildtaginfo('owner is null', ' tagdefs.owner is null'),         # system
                    buildtaginfo('owner is not null', ' tagdefs.owner is not null'), # userdefined
                    buildtaginfo('', '') )                                               # all

        def postCommit(results):
            system, userdefined, all = results
            apptarget = self.home + web.ctx.homepath
            all = ( all[0], all[1], all[2], all[3], all[4],
                    max(system[5], userdefined[5]) ) # use maximum length for user input boxes

            for acceptType in self.acceptTypesPreferedOrder():
                if acceptType == 'text/uri-list':
                    target = self.home + web.ctx.homepath
                    return self.render.FileTagUriList(target, all, urlquote)
                elif acceptType == 'text/html':
                    break
            # render HTML result
            if self.data_id:
                return self.renderlist("\"%s\" tags" % (self.data_id),
                                       [self.render.FileTagExisting('System', apptarget, self.data_id, system, urlquote),
                                        self.render.FileTagExisting('User', apptarget, self.data_id, userdefined, urlquote),
                                        self.render.FileTagNew(apptarget, self.data_id, self.typenames, all, lambda tag: self.isFileTagRestricted(tag), urlquote)])
            else:
                return self.renderlist("All tags for all files",
                                       [self.render.FileTagValExisting('System and User', apptarget, self.data_id, all, urlquote)])
            
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
            raise BadRequest(data="A non-empty tag name is required.")

        if not self.value:
            self.value = web.ctx.env['wsgi.input'].read()
        else:
            pass # we ignore body when value came from URI

        def body():
            results = self.select_tagdef(self.tag_id)
            if len(results) == 0:
                raise NotFound(data='tag definition %s' % self.tag_id)
            self.enforceFileTagRestriction(self.tag_id)
            self.set_file_tag(self.tag_id, self.value)
            return None

        def postCommit(results):
            return ''
            
        return self.dbtransact(body, postCommit)

    def DELETE(self, uri):
        # RESTful delete of exactly one tag on one file...
        if self.tag_id == '':
            raise BadRequest(data="A non-empty tag name is required.")
        
        def body():
            self.enforceFileTagRestriction(self.tag_id)
            self.delete_file_tag(self.tag_id, self.value)
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
                self.enforceFileTagRestriction(tag_id)
                self.set_file_tag(tag_id, self.tagvals[tag_id])
            return None

        def deleteBody():
            self.enforceFileTagRestriction(self.tag_id)
            self.delete_file_tag(self.tag_id, self.value)
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
                self.value = storage.value
            except:
                pass
        except:
            raise BadRequest(data="Error extracting form data.")

        if action == 'put':
            if len(self.tagvals) > 0:
                return self.dbtransact(putBody, postCommit)
            else:
                return self.dbtransact(nullBody, postCommit)
        elif action == 'delete':
            return self.dbtransact(deleteBody, postCommit)
        else:
            raise BadRequest(data="Form field action=%s not understood." % action)

class Query (Node):
    __slots__ = [ 'predlist', 'queryopts', 'action' ]
    def __init__(self, appname, predlist=[], queryopts={}):
        Node.__init__(self, appname)
        self.predlist = predlist
        self.queryopts = queryopts
        self.action = 'query'

    def qtarget(self):
        terms = []
        for pred in self.predlist:
            if pred['op']:
                terms.append(urlquote(pred['tag']) + pred['op'] + ",".join([ urlquote(val) for val in pred['vals'] ]))
            else:
                terms.append(urlquote(pred['tag']))
        return self.home + web.ctx.homepath + '/query/' + ';'.join(terms)

    def GET(self, uri):
        # this interface has both REST and form-based functions
        
        # test if user predicate equals a predicate from predlist
        def equals(pred, userpred):
            return ({'tag' : pred['tag'], 'op' : pred['op'], 'vals' : str(pred['vals'])} == userpred)

        tagname = None
        op = None
        value = []
        try:
            self.action = self.queryopts['action']
            tagname = self.queryopts['tag']
            op = self.queryopts['op']
            if self.action == 'add':
                for i in range(0,10):
                    val = self.queryopts['val' + str(i)]
                    if val != None:
                        value.append(val)
            elif self.action == 'delete':
                value = self.queryopts['vals']
        except:
            pass

        if op == '':
            op = None

        if op == None and self.action == 'delete':
            value = str([])

        userpred = { 'tag' : tagname, 'op' : op, 'vals' : value }

        if self.action == 'add':
            if userpred not in self.predlist:
                self.predlist.append( userpred )
        elif self.action == 'delete':
            self.predlist = [ pred for pred in self.predlist if not equals(pred, userpred) ]
        elif self.action == 'query':
            pass
        elif self.action == 'edit':
            pass
        else:
            raise BadRequest(data="Form field action=%s not understood." % self.action)

        def body():
            if len(self.predlist) > 0:
                files = [ res.file for res in self.select_files_by_predlist() ]
            else:
                files = []
            alltags = [ tagdef.tagname for tagdef in self.select_tagdefs() ]
            return ( files, alltags )

        def postCommit(results):
            files, alltags = results

            target = self.home + web.ctx.homepath

            if self.action in set(['add', 'delete']):
                raise web.seeother(self.qtarget() + '?action=edit')

            apptarget = self.home + web.ctx.homepath

            if len(self.predlist) == 0:
                # render a blank starting form
                return self.renderlist("Query by Tags",
                                       [self.render.QueryAdd(target, self.qtarget(), alltags, self.ops)])

            if self.action == 'query':
                for acceptType in self.acceptTypesPreferedOrder():
                    if acceptType == 'text/uri-list':
                        # return raw results for REST client
                        return self.render.FileUriList(target, files, urlquote)
                    elif acceptType == 'text/html':
                        break
                return self.renderlist("Query Results",
                                       [self.render.QueryViewStatic(self.qtarget(), self.predlist, dict(self.ops)),
                                        self.render.FileList(target, files, urlquote)])
            else:
                return self.renderlist("Query by Tags",
                                       [self.render.QueryAdd(target, self.qtarget(), alltags, self.ops),
                                        self.render.QueryView(self.qtarget(), self.predlist, dict(self.ops)),
                                        self.render.FileList(target, files, urlquote)])

        # this only runs if we need to do a DB query
        return self.dbtransact(body, postCommit)
