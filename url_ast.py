# define abstract syntax tree nodes for more readable code

import traceback
import sys
import web
import urllib
import re
import os
import webauthn
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote, idquote
from rest_fileio import FileIO, LogFileIO


def listmax(list):
    if len(list) > 0:
        return max(list)
    else:
        return 0
        
def dictmerge(base, custom):
    custom.update(base)
    return custom

class Node (object, Application):
    """Abstract AST node for all URI patterns"""

    __slots__ = [ 'appname' ]

    def __init__(self, appname):
        self.appname = appname
        Application.__init__(self)

    def uri2referer(self, uri):
        return self.home + uri

class TransmitNumber (Node):
    """Represents a transmitnumber URI

       POST tagfiler/transmitnumber
    """

    __slots__ = []

    def __init__(self, appname):
        Node.__init__(self, appname)

    def POST(self, uri):

        def body():
            result  = self.select_next_transmit_number()
            return result

        def postCommit(results):
            uri = self.home + '/transmitnumber/' + results
            web.header('Location', results)
            return results

        return self.dbtransact(body, postCommit)

class Study (Node):
    """Represents a study URI

       GET tagfiler/study?action=upload
    """

    __slots__ = []

    def __init__(self, appname, data_id=None, queryopts={}):
        Node.__init__(self, appname)
        self.action = 'get'
        self.study_type = None
        self.data_id = data_id
        self.status = None
        self.direction = 'upload'

    def body(self):
        tagnames = self.getParamsDb('applet tags', data_id=self.study_type)
        requiredtags = self.getParamsDb('applet tags require', data_id=self.study_type)
        
        if self.action == 'get' and self.data_id:
            files = [ res.file for res
                      in self.select_files_by_predlist([{'tag' : 'Transmission Number',
                                                         'op' : '=',
                                                         'vals' : [ self.data_id ]}]) ]
            tags = [ (tagname, [ res.value for res
                                 in self.select_file_tag(tagname=tagname,
                                                          data_id=self.data_id) ])
                     for tagname in tagnames if len(self.select_tagdef(tagname)) > 0]
            if self.status == 'success':
                self.txlog('STUDY %s OK REPORT' % self.direction.upper(), dataset=self.data_id)
            else:
                self.txlog('STUDY %s FAILURE REPORT' % self.direction.upper(), dataset=self.data_id)
        elif self.action == 'upload' or self.action == 'download':
            tags = [ (res.tagname, res.typestr) for res in self.select_tagdef() if res.tagname in tagnames]
            files = []
        else:
            tags = []
            files = []
        return (tags, files, tagnames, requiredtags)

    def postCommit(self, results):
        tags, files, tagnames, requiredtags = results
        target = self.home + web.ctx.homepath
        tvars = dict(target=target,
                     transmissionnum=self.data_id,
                     tags=tags,
                     files=files,
                     tagnames=tagnames,
                     requiredtags=requiredtags,
                     customproperties=self.customproperties,
                     direction=self.direction,
                     testfile=self.appletTest,
                     appletlog=self.appletlog,
                     idquote=idquote)
        if self.action == 'upload':
            return self.renderlist("Study Upload",
                                   [self.render.TreeUpload(tvars)])
        elif self.action == 'download':
            return self.renderlist("Study Download",
                                   [self.render.TreeDownload(tvars)])
        elif self.action == 'get':
            success = None
            error = None
            if self.status == 'success':
                success = 'All files were successfully %sed.' % self.direction
            elif self.status == 'error':
                error = 'An unknown error prevented a complete %s.' % self.direction
            else:
                error = self.status

            tvars['success'] = success
            tvars['error'] = error
                
            if self.data_id:
                return self.renderlist(None,
                                       [self.render.TreeStatus(tvars)])
            else:
                url = '/appleterror'
                if self.status:
                    url += '?status=%s' % urlquote(self.status)
                raise web.seeother(url)
        else:
            raise BadRequest('Unrecognized action form field.')

    def GET(self, uri):
        storage = web.input()
        try:
            self.action = storage.action
        except:
            pass

        try:
            self.study_type = storage.type
        except:
            pass

        try:
            self.direction = storage.direction
        except:
            pass

        try:
            self.status = storage.status
        except:
            pass

        return self.dbtransact(self.body, self.postCommit)

class AppletError (Node):
    """Represents an appleterror URI

       GET tagfiler/appleterror?status=string
    """

    __slots__ = []

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)
        self.action = None
        self.status = None

    def GET(self, uri):
        storage = web.input()
        try:
            self.status = storage.status
        except:
            pass

        # the applet needs to manage expiration itself
        # since it may be active while the html page is idle
        target = self.home + web.ctx.homepath
        self.setNoCache()
        return self.renderlist("Study Transfer Applet",
                               [self.render.AppletError(dict(status=self.status))])

class FileList (Node):
    """Represents a bare FILE/ URI

       GET  FILE  or FILE/         -- gives a listing
       GET  FILE?action=define     -- gives a new NameForm
       POST FILE?name=foo&type=t   -- redirects to GET FILE/name?type=t&action=define
    """

    __slots__ = []

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)

    def GET(self, uri):
        
        web.header('Content-Type', 'text/html;charset=ISO-8859-1')

        def body():
            tagdefs = [ (tagdef.tagname, tagdef)
                        for tagdef in self.select_tagdef() ]
            tagdefs = dict(tagdefs)
            
            if tagdefs.has_key('list on homepage'):
                self.predlist = [ { 'tag' : 'list on homepage', 'op' : None, 'vals' : [] } ]
            else:
                self.predlist=[]

            files = [ res for res in self.select_files_by_predlist() ]
            for res in files:
                # decorate each result with writeok information
                res.writeok = self.gui_test_file_authz('write',
                                                       owner=res.owner,
                                                       data_id=res.file,
                                                       local=res.local)

            roleinfo = self.buildroleinfo()

            return (files, tagdefs, roleinfo)

        def postCommit(results):
            target = self.home + web.ctx.homepath
            files, tagdefs, roleinfo = results
            tvars=dict(apptarget=web.ctx.homepath,
                       webauthnhome=self.webauthnhome,
                       help=self.help,
                       bugs=self.jira,
                       files=files,
                       referer=self.home + uri,
                       role=self.authn.role,
                       roles=self.authn.roles,
                       roleinfo=roleinfo,
                       urlquote=urlquote,
                       filelisttags=self.filelisttags,
                       filelisttagswrite=self.filelisttagswrite,
                       tagdefs=tagdefs,
                       idquote=idquote)
            self.setNoCache()
            return self.renderlist(None,
                                   [self.render.Commands(tvars),
                                    self.render.FileList(tvars)])

        storage = web.input()
        action = None
        name = None
        filetype = None
        readers = None
        writers = None
        try:
            action = storage.action
            try:
                name = storage.name
                filetype = storage.type
                readers = storage['read users']
                writers = storage['write users']
            except:
                pass
        except:
            pass

        if action == 'define':
            if name and filetype and readers and writers:
                if readers not in [ '*', 'owner' ]:
                    readers = 'owner'
                if writers not in [ '*', 'owner' ]:
                    writers = 'owner'
                if filetype not in [ 'file', 'url' ]:
                    filetype = 'file'

                url = self.home + web.ctx.homepath + '/file/' + urlquote(name)
                url += '?action=define'
                url += '&type=' + urlquote(filetype)
                if readers == '*':
                    url += '&read%20users=*'
                if writers == '*':
                    url += '&write%20users=*'
                raise web.seeother(url)
            else:
                return self.renderlist("Define a dataset",
                                       [self.render.NameForm(dict(apptarget=self.home + web.ctx.homepath))])
        else:
            return self.dbtransact(body, postCommit)

    def POST(self, uri):
        storage = web.input()
        name = None
        url = None
        try:
            action = storage.action
            name = storage.name
            url = storage.url
        except:
            raise BadRequest('Expected action, name, and url form fields.')
        ast = FileId(appname=self.appname,
                     data_id=name,
                     location=url,
                     local=False)
        ast.preDispatchFake(uri, self)
        return ast.POST(uri)

class LogList (Node):
    """Represents a bare LOG/ URI

       GET LOG or LOG/  -- gives a listing
       """

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)

    def GET(self, uri):
        if 'admin' not in self.authn.roles:
            raise Forbidden('listing of log files')
        
        if self.log_path:
            lognames = sorted(os.listdir(self.log_path), reverse=True)
                              
        else:
            lognames = []
        
        target = self.home + web.ctx.homepath
        tvars = dict(target=target,
                     files=lognames,
                     urlquote=urlquote)
        
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                # return raw results for REST client
                return self.render.LogUriList(tvars)
            elif acceptType == 'text/html':
                break
        return self.renderlist("Available logs",
                               [self.render.LogList(tvars)])

class Contact (Node):
    """Represents a bare CONTACT URI

       GET CONTACT
       """

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)

    def GET(self, uri):
        
        tvars = dict(target=self.home + web.ctx.homepath,
                     contact=self.contact)
        self.setNoCache()
        return self.renderlist("Contact Us",
                               [self.render.Contact(tvars)])

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

class LogId(Node, LogFileIO):
    """Represents a direct LOG/data_id URI

       Just creates filename and lets LogFileIO do the work.

    """
    __slots__ = [ 'data_id' ]
    def __init__(self, appname, data_id, queryopts={}):
        Node.__init__(self, appname)
        LogFileIO.__init__(self)
        self.data_id = data_id
        self.queryopts = queryopts

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

    __slots__ = [ 'tag_id', 'typestr', 'target', 'action', 'tagdefs', 'writepolicy', 'readpolicy', 'multivalue', 'queryopts' ]

    def __init__(self, appname, tag_id=None, typestr=None, queryopts={}):
        Node.__init__(self, appname)
        self.tag_id = tag_id
        self.typestr = typestr
        self.writepolicy = None
        self.readpolicy = None
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
            predefined = [ ( tagdef.tagname, tagdef.typestr, tagdef.multivalue, tagdef.readpolicy, tagdef.writepolicy, None)
                     for tagdef in self.select_tagdef(where='owner is null', order='tagname') ]
            userdefined = [ ( tagdef.tagname, tagdef.typestr, tagdef.multivalue, tagdef.readpolicy, tagdef.writepolicy, tagdef.owner)
                     for tagdef in self.select_tagdef(where='owner is not null', order='tagname') ]
            
            return (predefined, userdefined)

        def postCommit(tagdefs):
            web.header('Content-Type', 'text/html;charset=ISO-8859-1')
            self.setNoCache()
            predefined, userdefined = tagdefs
            tvars = dict(target=self.target,
                         typenames=self.typenames,
                         test_tagdef_authz=lambda mode, tag: self.test_tagdef_authz(mode, tag),
                         urlquote=urlquote)
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting(dictmerge(tvars, dict(tagdefs=userdefined, title='User'))),
                                    self.render.TagdefExisting(dictmerge(tvars, dict(tagdefs=predefined, title='System')))])

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
                self.setNoCache()
                return ('typestr=' + urlquote(tagdef.typestr) 
                        + '&readpolicy=' + urlquote(unicode(tagdef.readpolicy))
                        + '&writepolicy=' + urlquote(unicode(tagdef.writepolicy))
                        + '&multivalue=' + urlquote(unicode(tagdef.multivalue))
                        + '&owner=' + urlquote(unicode(tagdef.owner)))
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
            self.enforce_tagdef_authz('write')
            self.delete_tagdef()
            return ''

        def postCommit(results):
            self.log('DELETE', tag=self.tag_id)
            return ''

        if len(self.queryopts) > 0:
            raise BadRequest(data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)
                
    def PUT(self, uri):

        if self.tag_id == None:
            raise BadRequest(data="Tag definitions require a non-empty tag name.")

        # self.typestr and self.writepolicy take precedence over queryopts...

        if self.typestr == None:
            try:
                self.typestr = self.queryopts['typestr']
            except:
                self.typestr = ''

        if self.readpolicy == None:
            try:
                self.readpolicy = self.queryopts['readpolicy'].lower()
            except:
                self.readpolicy = 'fowner'

        if self.writepolicy == None:
            try:
                self.writepolicy = self.queryopts['writepolicy'].lower()
            except:
                self.writepolicy = 'fowner'

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
            self.log('CREATE', tag=self.tag_id)
            raise web.seeother('/tagdef/' + urlquote(self.tag_id))

        return self.dbtransact(body, postCommit)

    def POST(self, uri):

        storage = web.input()
        try:
            self.action = storage.action
            for key in storage.keys():
                if key[0:4] == 'tag-':
                    if storage[key] != '':
                        try:
                            typestr = storage['type-%s' % (key[4:])]
                        except:
                            raise BadRequest(data="A tag type must be specified.")
                        try:
                            readpolicy = storage['readpolicy-%s' % (key[4:])]
                        except:
                            raise BadRequest(data="A read policy must be specified.")
                        try:
                            writepolicy = storage['writepolicy-%s' % (key[4:])]
                        except:
                            raise BadRequest(data="A write policy must be specified.")
                        try:
                            multivalue = storage['multivalue-%s' % (key[4:])]
                        except:
                            raise BadRequest(data="The value cardinality must be specified.")
                        self.tagdefs[storage[key]] = (typestr, readpolicy, writepolicy, multivalue)
            try:
                self.tag_id = storage.tag
            except:
                pass
        except BadRequest:
            raise
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception during tagdef form post',
                      traceback.format_exception(et, ev, tb))
            raise BadRequest(data="Error extracting form data.")

        def body():
            if self.action == 'add':
                for tagname in self.tagdefs.keys():
                    self.tag_id = tagname
                    self.typestr, self.readpolicy, self.writepolicy, self.multivalue = self.tagdefs[tagname]
                    results = self.select_tagdef(self.tag_id)
                    if len(results) > 0:
                        raise Conflict(data="Tag %s is already defined." % self.tag_id)
                    self.insert_tagdef()
                    self.log('CREATE', tag=self.tag_id)
            elif self.action == 'delete' or self.action == 'CancelDelete':
                self.enforce_tagdef_authz('write')
                return None
            elif self.action == 'ConfirmDelete':
                self.enforce_tagdef_authz('write')
                self.delete_tagdef()
                self.log('DELETE', tag=self.tag_id)
            else:
                raise BadRequest(data="Form field action=%s not understood." % self.action)
            return None

        def postCommit(results):
            if self.action == 'delete':
                return self.renderlist("Delete Confirmation",
                                       [self.render.ConfirmForm(dict(target=self.home + web.ctx.homepath,
                                                                     type='tagdef',
                                                                     name=self.tag_id,
                                                                     referer=self.uri2referer(uri),
                                                                     urlquote=urlquote))])
            else:
                # send client back to get form page again
                raise web.seeother('/tagdef')

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/data_id URIs"""

    __slots__ = [ 'data_id', 'tag_id', 'value', 'tagvals' ]

    def __init__(self, appname, data_id=None, tag_id='', value=None, tagvals=None, queryopts={}):
        Node.__init__(self, appname)
        self.data_id = data_id
        self.tag_id = tag_id
        self.value = value
        self.apptarget = self.home + web.ctx.homepath
        self.view_type = None
        self.referer = None
        if tagvals:
            self.tagvals = tagvals
        else:
            self.tagvals = dict()

    def mystr(self, val):
        if type(val) == type(1.0):
            return re.sub("0*e", "0e", "%.48e" % val)
        else:
            return str(val)

    def get_tag_body(self):
        results = self.select_tagdef(self.tag_id)
        if len(results) == 0:
            raise NotFound(data='tag definition %s' % self.tag_id)
        tagdef = results[0]
        owner = self.owner()
        results = self.select_file_tag(self.tag_id, self.value, tagdef=tagdef, owner=owner)
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
        self.txlog('GET', dataset=self.data_id, tag=self.tag_id)
        return values

    def get_tag_postCommit(self, values):
        web.header('Content-Type', 'application/x-www-form-urlencoded')
        if len(values) > 0:
            return "&".join([(urlquote(self.tag_id) + '=' + urlquote(self.mystr(val))) for val in values])
        else:
            return urlquote(self.tag_id)

    def buildtaginfo(self, ownerwhere):
        owner = self.owner()
        where1 = ''
        where2 = ''
        if ownerwhere:
            where1 = 'owner %s' % ownerwhere
            where2 = 'tagdefs.owner %s' % ownerwhere
        filtered_tagdefs = self.select_tagdef(where=where1, order='tagname')
        filtered_filetags = self.select_filetags(where=where2)
        custom_tags = self.getParamsDb('tag list tags', data_id=self.view_type)
        tagdefs = [ (tagdef.tagname,
                     tagdef.typestr,
                     self.test_tag_authz('write', tagdef.tagname, fowner=owner))
                    for tagdef in filtered_tagdefs
                    if (not custom_tags or tagdef.tagname in custom_tags) ]
        tagdefsdict = dict([ (tagdef[0], tagdef) for tagdef in tagdefs ])
        filetags = [ (result.file, result.tagname)
                     for result in filtered_filetags
                     if self.test_tag_authz('read', result.tagname, fowner=owner)
                     and (not custom_tags or result.tagname in custom_tags) ]
        filetagvals = [ (file,
                         tag,
                         [self.mystr(val) for val in self.gettagvals(tag, data_id=file, owner=owner)])
                        for file, tag in filetags ]
        length = listmax([listmax([ len(val) for val in vals]) for file, tag, vals in filetagvals])
        return ( self.systemTags, # excludes
                 tagdefs,
                 tagdefsdict,
                 filetags,
                 filetagvals,
                 length )

    def GETtag(self, uri):
        # RESTful get of exactly one tag on one file...
        return self.dbtransact(self.get_tag_body, self.get_tag_postCommit)

    def get_all_body(self):
        self.txlog('GET ALL TAGS', dataset=self.data_id)
        return (self.buildtaginfo('is null'),     # system
                self.buildtaginfo('is not null'), # userdefined
                self.buildtaginfo(''),            # all
                self.buildroleinfo(),             # roleinfo
                self.buildtagnameinfo())          # tagnameinfo

    def get_title_one(self):
        return 'Tags for dataset "%s"' % self.data_id

    def get_title_all(self):
        return 'Tags for all datasets'

    def get_all_html_render(self, results):
        system, userdefined, all, roleinfo, tagnameinfo = results
        #web.debug(system, userdefined, all)
        tvars = dict(apptarget=self.apptarget,
                     tagspace='tags',
                     typenames=self.typenames,
                     data_id=self.data_id,
                     roleinfo=roleinfo,
                     tagnameinfo=tagnameinfo,
                     urlquote=urlquote,
                     idquote=idquote)
        if self.data_id:
            return self.renderlist(self.get_title_one(),
                                   [self.render.FileTagExisting(dictmerge(tvars, dict(title='User', taginfo=userdefined))),
                                    self.render.FileTagExisting(dictmerge(tvars, dict(title='System', taginfo=system))),
                                    self.render.TagdefNewShortcut(dictmerge(tvars, dict(title='Define more tags')))])
        else:
            return self.renderlist(self.get_title_all(),
                                   [self.render.FileTagValExisting(dictmerge(tvars, dict(title='', taginfo=all)))])      

    def get_all_postCommit(self, results):
        system, userdefined, all, roleinfo, tagnameinfo = results
        all = ( all[0], all[1], all[2], all[3], all[4],
                max(system[5], userdefined[5]) ) # use maximum length for user input boxes

        tvars = dict(target=self.home + web.ctx.homepath,
                     taginfo=all,
                     urlquote=urlquote)

        self.setNoCache()
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                return self.render.FileTagUriList(tvars)
            elif acceptType == 'application/x-www-form-urlencoded':
                web.header('Content-Type', 'application/x-www-form-urlencoded')
                body = []
                for file, tag, vals in all[4]:
                    if len(vals) > 0:
                        for val in vals:
                            body.append("%s=%s" % (urlquote(tag), urlquote(val)))
                    else:
                        body.append("%s" % (urlquote(tag)))
                return '&'.join(body)
            elif acceptType == 'text/html':
                break
        # render HTML result
        return self.get_all_html_render(results)
        
    def GETall(self, uri):
        # HTML get of all tags on one file...
        return self.dbtransact(self.get_all_body, self.get_all_postCommit)

    def GET(self, uri=None):
        # dispatch variants, browsing and REST
        storage = web.input()
        try:
            self.view_type = storage.view
        except:
            pass
        keys = self.tagvals.keys()
        if len(keys) == 1:
            self.tag_id = keys[0]
            vals = self.tagvals[self.tag_id]
            if len(vals) == 1:
                self.value = vals[0]
            elif len(vals) > 1:
                raise BadRequest(data="GET does not support multiple values in the URI.")
            return self.GETtag(uri)
        elif len(keys) > 1:
            raise BadRequest(data="GET does not support multiple tag names in the URI.")
        else:
            return self.GETall(uri)

    def put_body(self):
        try:
            # custom DEI EIU hack, proxy tag ops on Image Set to all member files
            results = self.select_file_tag('Image Set')
            if len(results) > 0:
                predlist = [ { 'tag' : 'Transmission Number', 'op' : '=', 'vals' : [self.data_id] } ]
                subfiles = [ res.file for res in  self.select_files_by_predlist(predlist=predlist) ]
            else:
                subfiles = []
        except:
            subfiles = []
        for tag_id in self.tagvals.keys():
            results = self.select_tagdef(tag_id)
            if len(results) == 0:
                raise NotFound(data='tag definition %s' % tag_id)
            self.enforce_tag_authz('write', tag_id)
            for value in self.tagvals[tag_id]:
                self.set_file_tag(tag_id, value)
                self.txlog('SET', dataset=self.data_id, tag=tag_id, value=value)
                if tag_id in [ 'read users', 'write users', 'owner' ]:
                    for subfile in subfiles:
                        self.enforce_tag_authz('write', tag_id, data_id=subfile)
                        self.txlog('SET', dataset=subfile, tag=tag_id, value=value)
                        self.set_file_tag(tag_id, value, data_id=subfile)
        return None

    def put_postCommit(self, results):
        return ''

    def PUT(self, uri):
        try:
            content_type = web.ctx.env['CONTENT_TYPE'].lower()
        except:
            content_type = 'text/plain'

        content = web.ctx.env['wsgi.input'].read()
        if content_type == 'application/x-www-form-urlencoded':
            # handle same entity body format we output in GETtag()
            #  tag=val&tag=val...
            for tagval in content.strip().split('&'):
                tag, val = tagval.split('=')
                tag = urllib.unquote(tag)
                val = urllib.unquote(val)

                if tag == '':
                    raise BadRequest(data="A non-empty tag name is required.")

                try:
                    vals = self.tagvals[tag]
                except:
                    self.tagvals[tag] = []
                    vals = self.tagvals[tag]
                vals.append(val)
                
        return self.dbtransact(self.put_body, self.put_postCommit)

    def delete_body(self):
        try:
            # custom DEI EIU hack
            results = self.select_file_tag('Image Set')
            if len(results) > 0:
                predlist = [ { 'tag' : 'Transmission Number', 'op' : '=', 'vals' : [self.data_id] } ]
                subfiles = [ res.file for res in  self.select_files_by_predlist(predlist=predlist) ]
            else:
                subfiles = []
        except:
            subfiles = []
        self.enforce_tag_authz('write')
        self.txlog('DELETE', dataset=self.data_id, tag=self.tag_id, value=self.value)
        self.delete_file_tag(self.tag_id, self.value)
        if self.tag_id in [ 'read users', 'write users' ]:
            for subfile in subfiles:
                self.enforce_tag_authz('write', self.tag_id, data_id=subfile)
                self.txlog('DELETE', dataset=subfile, tag=self.tag_id, value=self.value)
                self.delete_file_tag(self.tag_id, self.value, data_id=subfile)
        return None

    def delete_postCommit(self, results):
        return ''

    def DELETE(self, uri):
        # RESTful delete of exactly one tag on one file...
        keys = self.tagvals.keys()
        if len(keys) == 1:
            self.tag_id = keys[0]
            vals = self.tagvals[self.tag_id]
            if len(vals) == 1:
                self.value = vals[0]
            elif len(vals) > 1:
                raise BadRequest(data="DELETE does not support multiple values in the URI.")
        elif len(keys) > 1:
            raise BadRequest(data="DELETE does not support multiple tag names in the URI.")

        if self.tag_id == '':
            raise BadRequest(data="A non-empty tag name is required.")
        
        return self.dbtransact(self.delete_body, self.delete_postCommit)

    def post_nullBody(self):
        web.debug('post_nullBody')
        return None

    def post_postCommit(self, results):
        if self.referer == None:
            self.referer = '/tags/' + urlquote(self.data_id)
        raise web.seeother(self.referer)

    def POST(self, uri):
        # simulate RESTful actions and provide helpful web pages to browsers
        storage = web.input()
        try:
            action = storage.action
            for key in storage.keys():
                if key[0:4] == 'set-':
                    tag_id = key[4:]
                    try:
                        value = storage['val-%s' % (tag_id)]
                    except:
                        value = None
                    self.tagvals[urllib.unquote(tag_id)] = [ value ]
            try:
                # look for single tag/value for backwards compatibility
                self.tag_id = storage.tag
                try:
                    self.value = storage.value
                except:
                    pass
                if self.tag_id:
                    self.tagvals[self.tag_id] = [ self.value ]
            except:
                pass
            try:
                self.referer = storage.referer
            except:
                self.referer = None
        except:
            raise BadRequest(data="Error extracting form data.")

        if action == 'put':
            if len(self.tagvals) > 0:
                #web.debug(self.tagvals)
                return self.dbtransact(self.put_body, self.post_postCommit)
            else:
                return self.dbtransact(self.post_nullBody, self.post_postCommit)
        elif action == 'delete':
            return self.dbtransact(self.delete_body, self.post_postCommit)
        else:
            raise BadRequest(data="Form field action=%s not understood." % action)

class TagdefACL (FileTags):
    """Reuse FileTags plumbing but map file/tagname to tagdef/role-users."""
    __slots__ = [ ]
    def __init__(self, appname, data_id=None, tag_id='', value=None, tagvals=None):
        FileTags.__init__(self, appname, data_id, tag_id, value, tagvals)

    def get_tag_body(self):
        """Override FileTags.get_tag_body to consult tagdef ACL instead"""
        results = self.select_tagdef(self.data_id)
        if len(results) == 0:
            raise NotFound(data='tag definition "%s"' % self.data_id)
        tagdef = results[0]
        acl = self.tag_id.lower()
        if acl not in [ 'readers', 'writers' ]:
            raise BadRequest(data='Tag definition ACL %s not understood.' % acl)
        m1 = dict(readers='readpolicy', writers='writepolicy')
        m2 = dict(readers='read', writers='write')
        mode = m2[acl]
        policy = tagdef[m1[acl]]
        if policy != 'tag':
            raise Conflict(data=('Tagdef "%s", with %s=%s, does not use ACLs.'
                                 % (self.data_id, m1[acl], policy)))
        results = self.select_tag_acl(mode, self.value, tag_id=self.data_id)
        if len(results) == 0:
            if self.value == None:
                pass
            elif self.value == '':
                raise NotFound(data='ACL %s = "" on tagdef %s' % (self.tag_id, self.data_id))
            else:
                raise NotFound(data='ACL %s = %s on tagdef %s' % (self.tag_id, self.value, self.data_id))
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

    def buildaclinfo(self):
        results = self.select_tagdef(self.data_id)
        if len(results) == 0:
            raise NotFound(data='tag definition "%s"' % self.data_id)
        tagdef = results[0]
        acldefs = [ ('readers', 'role', tagdef.owner in self.authn.roles and tagdef.readpolicy == 'tag'),
                    ('writers', 'role', tagdef.owner in self.authn.roles and tagdef.writepolicy == 'tag') ]
        acldefsdict = dict([ (acldef[0], acldef) for acldef in acldefs ])
        readacls = [ (result.tagname, 'readers')
                     for result in self.select_tagdef(tagname=self.data_id,
                                                      where="readpolicy = 'tag'") ]
        writeacls = [ (result.tagname, 'writers')
                      for result in self.select_tagdef(tagname=self.data_id,
                                                       where="writepolicy = 'tag'") ]
        tagacls = readacls + writeacls
        m = dict(readers='read', writers='write')
        tagaclvals = [ (tag,
                        acl,
                        [result.value for result in self.select_tag_acl(m[acl], tag_id=tag)])
                       for tag, acl in tagacls ]
        length = listmax([listmax([ len(val) for val in vals]) for tag, acl, vals in tagaclvals])
        return ( [],
                 acldefs,
                 acldefsdict,
                 tagacls,
                 tagaclvals,
                 length )

    def get_all_body(self):
        """Override FileTags.get_all_body to consult tagdef ACL instead"""
        aclinfo = self.buildaclinfo()
        return ( ( [], [], {}, [], [], 0 ),
                 ( [], [], {}, [], [], 0 ),
                 aclinfo,
                 self.buildroleinfo() )

    def get_title_one(self):
        return 'ACLs for tag "%s"' % self.data_id

    def get_title_all(self):
        return 'ACLs for all tags'

    def get_all_html_render(self, results):
        system, userdefined, all, roleinfo = results
        tvars = dict(apptarget=self.apptarget,
                     tagspace='tagdefacl',
                     typenames=self.typenames,
                     data_id=self.data_id,
                     roleinfo=roleinfo,
                     urlquote=urlquote,
                     idquote=idquote)
        if self.data_id:
            return self.renderlist(self.get_title_one(),
                                   [self.render.FileTagExisting(dictmerge(tvars, dict(title='', taginfo=all))),
                                    self.render.FileTagNew(dictmerge(tvars, dict(title='Add an authorized user', taginfo=all)))])
        else:
            return self.renderlist(self.get_title_all(),
                                   [self.render.FileTagValExisting(dictmerge(tvars, dict(title='', taginfo=all)))])       

    def put_body(self):
        """Override FileTags.put_body to consult tagdef ACL instead"""
        self.enforce_tagdef_authz('write', tag_id=self.data_id)
        for acl in self.tagvals.keys():
            for value in self.tagvals[acl]:
                self.set_tag_acl(dict(writers='write', readers='read')[acl],
                                 value, self.data_id)
                self.txlog('SET', tag=self.data_id, mode=acl, user=value)
        return None

    def delete_body(self):
        """Override FileTags.put_body to consult tagdef ACL instead"""
        self.enforce_tagdef_authz('write', tag_id=self.data_id)
        self.delete_tag_acl(dict(writers='write', readers='read')[self.tag_id],
                            self.value, self.data_id)
        return None
    
    def post_putBody(self):
        for tag_id in self.tagvals:
            self.enforce_tagdef_authz('write', tag_id=self.data_id)
            self.set_tag_acl(dict(writers='write', readers='read')[tag_id],
                             self.tagvals[tag_id], self.data_id)
            self.txlog('SET', tag=self.data_id, mode=tag_id, user=self.tagvals[tag_id])
        return None

    def post_deleteBody(self):
        self.enforce_tagdef_authz('write', tag_id=self.data_id)
        self.delete_tag_acl(dict(writers='write', readers='read')[self.tag_id],
                            self.value, self.data_id)
        self.txlog('DELETE', tag=self.data_id, mode=self.tag_id, user=self.value)
        return None

    def post_postCommit(self, results):
        url = '/tagdefacl/' + urlquote(self.data_id)
        raise web.seeother(url)

class Query (Node):
    __slots__ = [ 'predlist', 'queryopts', 'action' ]
    def __init__(self, appname, predlist=[], queryopts={}):
        Node.__init__(self, appname)
        self.predlist = predlist
        self.queryopts = queryopts
        self.action = 'query'
        self.title = None

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

        try:
            self.title = self.queryopts['title']
        except:
            self.title = None

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
            files = [ res for res in self.select_files_by_predlist() ]
            for res in files:
                # decorate each result with writeok information
                res.writeok = self.gui_test_file_authz('write',
                                                       owner=res.owner,
                                                       data_id=res.file,
                                                       local=res.local)
            alltagdefs = [ tagdef for tagdef in self.select_tagdef(order='tagname', staticauthz='read') ]
            roleinfo = self.buildroleinfo()
            return ( files, alltagdefs, roleinfo )

        def postCommit(results):
            files, tagdefs, roleinfo = results
            apptarget = self.home + web.ctx.homepath

            tvars = dict(role=self.authn.role,
                         roles=self.authn.roles,
                         roleinfo=roleinfo,
                         files=files,
                         tags=[tagdef.tagname for tagdef in tagdefs],
                         ops=self.ops,
                         home=web.ctx.homepath,
                         apptarget=apptarget,
                         qtarget=self.qtarget(),
                         predlist=self.predlist,
                         urlquote=urlquote,
                         referer=self.home + uri,
                         filelisttags=self.filelisttags,
                         filelisttagswrite=self.filelisttagswrite,
                         tagdefs=dict([(tagdef.tagname, tagdef) for tagdef in tagdefs]),
                         idquote=idquote)

            self.setNoCache()

            if self.action in set(['add', 'delete']):
                raise web.seeother(self.qtarget() + '?action=edit')

            if self.title == None:
                if self.action == 'query':
                    self.title = "Query Results"
                else:
                    self.title = "Query by Tags"

            if self.action == 'query':
                for acceptType in self.acceptTypesPreferedOrder():
                    if acceptType == 'text/uri-list':
                        # return raw results for REST client
                        return self.render.FileUriList(tvars)
                    elif acceptType == 'text/html':
                        break
                return self.renderlist(self.title,
                                       [self.render.QueryViewStatic(tvars),
                                        self.render.FileList(tvars)])
            else:
                return self.renderlist(self.title,
                                       [self.render.QueryAdd(tvars),
                                        self.render.QueryView(tvars),
                                        self.render.FileList(tvars)])

        return self.dbtransact(body, postCommit)
