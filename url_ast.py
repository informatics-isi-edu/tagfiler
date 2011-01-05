# define abstract syntax tree nodes for more readable code

import traceback
import sys
import web
import urllib
import re
import os
import webauthn
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote, urlunquote, idquote, jsonWriter
from rest_fileio import FileIO, LogFileIO
import json

jsonMungeTypes = set([ 'date', 'timestamptz' ])

def listmax(list):
    if list:
        return max([len(mystr(val)) for val in list])
    else:
        return 0

def listOrStringMax(val, curmax=0):
    if type(val) == list:
        return max(listmax(val), curmax)
    elif val:
        return max(len(mystr(val)), curmax)
    else:
        return curmax

def mystr(val):
    if type(val) == type(1.0):
        return re.sub("0*e", "0e", "%.48e" % val)
    else:
        return str(val)

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
        self.study_size = None
        self.count = None
        self.data_id = data_id
        self.status = None
        self.direction = 'upload'

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

        def body():
            files = []
    
            self.globals['appletTagnames'] = self.getParamsDb('applet tags', data_id=self.study_type)
            self.globals['types'] = self.get_type()
            self.globals['appletTagnamesRequire'] = self.getParamsDb('applet tags require', data_id=self.study_type)
            
            if self.action == 'get' and self.data_id:
                files = self.gettagvals('contains', data_id=self.data_id)
                self.globals['appletTagvals'] = [ (tagname,
                                                   [ res.value for res
                                                     in self.select_file_tag(tagname=tagname, data_id=self.data_id) ])
                                                  for tagname in self.globals['appletTagnames'] ]
            elif self.action == 'upload' or self.action == 'download':
                self.globals['tagdefsdict'] = dict([ item for item in self.globals['tagdefsdict'].iteritems()
                                                     if item[0] in self.globals['appletTagnames'] ])
            return files
    
        def postCommit(files):
            if self.action == 'upload':
                return self.renderlist("Study Upload",
                                       [self.render.TreeUpload()])
            elif self.action == 'download':
                return self.renderlist("Study Download",
                                       [self.render.TreeDownload(self.data_id)])
            elif self.action == 'get':
                success = None
                error = None
                if self.status == 'success':
                    success = 'All files were successfully %sed.' % self.direction
                elif self.status == 'error':
                    error = 'An unknown error prevented a complete %s.' % self.direction
                else:
                    error = self.status
    
                if self.data_id:
                    return self.renderlist(None,
                                           [self.render.TreeStatus(self.data_id, self.direction, success, error, files)])
                else:
                    url = '/appleterror'
                    if self.status:
                        url += '?status=%s' % urlquote(self.status)
                    raise web.seeother(url)
            else:
                raise BadRequest('Unrecognized action form field.')

        return self.dbtransact(body, postCommit)

    def PUT(self, uri):
        storage = web.input()
        try:
            self.study_size = int(storage.study_size)
        except:
            pass

        try:
            self.count = int(storage.count)
        except:
            pass

        try:
            self.status = storage.status
        except:
            pass

        try:
            self.direction = storage.direction
        except:
            pass

        def body():
            result = True
            if self.direction == 'upload' and self.status == 'success':
                results = self.select_dataset_size()[0]
                if results.size != self.study_size or results.count != self.count:
                    self.status = 'conflict'
                    result = None
            if self.status == 'success':
                self.txlog('STUDY %s OK REPORT' % self.direction.upper(), dataset=self.data_id)
            else:
                self.txlog('STUDY %s FAILURE REPORT' % self.direction.upper(), dataset=self.data_id)
            return result

        def postCommit(result):
            if not result:
                raise Conflict('The size of the uploaded dataset "%s" does not match original file(s) size.' % (self.data_id))

        return self.dbtransact(body, postCommit)

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
                               [self.render.AppletError(self.status)])

class FileList (Node):
    """Represents a bare FILE/ URI

       GET  FILE  or FILE/         -- gives a listing
       GET  FILE?action=define     -- gives a new NameForm
       POST FILE?name=foo&type=t   -- redirects to GET FILE/name?type=t&action=define
    """

    __slots__ = []

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)
        self.globals['view'] = None
        self.queryopts = queryopts

    def GET(self, uri):
        
        web.header('Content-Type', 'text/html;charset=ISO-8859-1')
        self.globals['referer'] = self.home + uri

        def body():
            tagdefs = [ (tagdef.tagname, tagdef)
                        for tagdef in self.select_tagdef() ]

            listtags = self.queryopts.get('list', None)
            if listtags:
                if type(listtags) != set:
                    listtags = [ listtags ]
                self.globals['filelisttags'] = [ tag for tag in listtags if tag ]
            else:
                self.globals['filelisttags'] = self.getParamsDb('file list tags', data_id=self.globals['view'])
            self.globals['filelisttagswrite'] = self.getParamsDb('file list tags write', data_id=self.globals['view'])
            
            if self.globals['tagdefsdict'].has_key('list on homepage'):
                self.predlist = [ { 'tag' : 'list on homepage', 'op' : None, 'vals' : [] } ]
            else:
                self.predlist=[]

            files = [ res for res in self.select_files_by_predlist(listtags=self.globals['filelisttags'] + ['Image Set']) ]
            for res in files:
                # decorate each result with writeok information
                res.writeok = self.gui_test_file_authz('write',
                                                       owner=res.owner,
                                                       data_id=res.file,
                                                       local=res.local)

            return files

        def postCommit(files):
            target = self.home + web.ctx.homepath
            self.setNoCache()
            return self.renderlist(None,
                                   [self.render.Commands(),
                                    self.render.FileList(files)])

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
                                       [self.render.NameForm()])
        else:
            try:
                self.globals['view'] = storage.view
            except:
                pass
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
        
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                # return raw results for REST client
                return self.render.LogUriList(lognames)
            elif acceptType == 'text/html':
                break
        return self.renderlist("Available logs",
                               [self.render.LogList(lognames)])

class Contact (Node):
    """Represents a bare CONTACT URI

       GET CONTACT
       """

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)

    def GET(self, uri):
        
        self.setNoCache()
        return self.renderlist("Contact Us",
                               [self.render.Contact()])

class FileId(Node, FileIO):
    """Represents a direct FILE/data_id URI

       Just creates filename and lets FileIO do the work.

    """
    __slots__ = [ 'data_id', 'location', 'local', 'queryopts' ]
    def __init__(self, appname, data_id, location=None, local=False, queryopts={}):
        Node.__init__(self, appname)
        FileIO.__init__(self)
        if type(data_id) == web.utils.Storage:
            self.data_id = data_id.data_id
            self.version = data_id.version
        else:
            self.data_id = data_id
            self.version = None
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
            types = self.get_type()
            
            return (predefined, userdefined, types)

        def postCommit(defs):
            web.header('Content-Type', 'text/html;charset=ISO-8859-1')
            self.setNoCache()
            predefined, userdefined, types = defs
            test_tagdef_authz = lambda mode, tag: self.test_tagdef_authz(mode, tag)
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting('User', test_tagdef_authz),
                                    self.render.TagdefExisting('System', test_tagdef_authz)])

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
                self.globals['data_id'] = self.tag_id
                return self.renderlist("Delete Confirmation",
                                       [self.render.ConfirmForm('tagdef')])
            else:
                # send client back to get form page again
                raise web.seeother('/tagdef')

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/data_id URIs"""

    __slots__ = [ 'data_id', 'tag_id', 'value', 'tagvals' ]

    def __init__(self, appname, data_id=None, tag_id='', value=None, tagvals=None, queryopts={}):
        Node.__init__(self, appname)
        if type(data_id) == web.utils.Storage:
            self.data_id = data_id.data_id
            self.version = data_id.version
        else:
            self.data_id = data_id
            self.version = None
        self.tag_id = tag_id
        self.value = value
        self.typestr = None
        self.view_type = None
        self.referer = None
        if tagvals:
            self.tagvals = tagvals
        else:
            self.tagvals = dict()
        self.queryopts = queryopts

        self.globals['data_id'] = self.data_id 
        self.globals['version'] = self.version

    def get_tag_body(self):
        owner = self.owner()
        results = self.select_tagdef(self.tag_id)
        if len(results) == 0:
            raise NotFound(data='tag definition "%s"' % self.tag_id)
        tagdef = results[0]
        tagdef.writeok = self.test_tag_authz('write', tagdef.tagname, fowner=owner)
        self.tagdef = tagdef
        self.typestr = tagdef.typestr
        self.contentType = None
        self.urlFallback = False
        
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType in set([ 'application/x-www-form-urlencoded',
                                   'text/plain' ]):
                self.contentType = acceptType
                break
            if acceptType == 'text/uri-list':
                if self.typestr == 'url':
                    # only prefer uri-list for URLs
                    self.contentType = acceptType
                else:
                    # but use it as last resort for other types
                    self.urlFallback = True
                break
            if acceptType == 'text/html':
                break

        if self.contentType == None and self.urlFallback:
            self.contentType = 'text/uri-list'

        if self.contentType == None:
            self.contentType = 'text/html'
        
        results = self.select_file()
        if len(results) == 0:
            raise NotFound(data='data set "%s"' % self.data_id)
        owner = self.owner()
        results = self.select_file_tag(self.tag_id, self.value, tagdef=tagdef, owner=owner)
        if len(results) == 0 and self.contentType not in ['text/uri-list', 'text/html']:
            if self.value == None:
                raise NotFound(data='tag "%s" on dataset "%s"' % (self.tag_id, self.data_id))
            elif self.value == '':
                raise NotFound(data='tag "%s" = "" on dataset "%s"' % (self.tag_id, self.data_id))
            else:
                raise NotFound(data='tag "%s" = "%s" on dataset "%s"' % (self.tag_id, self.value, self.data_id))
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
        web.header('Content-Type', self.contentType)
        if self.contentType == 'application/x-www-form-urlencoded':
            if len(values) > 0:
                return "&".join([(urlquote(self.tag_id) + '=' + urlquote(mystr(val))) for val in values])
            else:
                return urlquote(self.tag_id)
        elif self.contentType == 'text/uri-list':
            if self.typestr == 'url':
                return '\n'.join(values + [''])
            if self.typestr == 'file':
                return '\n'.join(['%s/%s/file/%s' % (self.home, web.ctx.homepath, urlquote_name(val)) for val in values]
                                 + [''])
            else:
                raise Conflict('Content-Type text/uri-list not appropriate for tag type "%s"' % self.typestr)
        elif self.contentType == 'text/plain':
            return '\n'.join(values) + '\n'
        else:
            # 'text/html'
            file = web.storage(file=self.data_id)
            file[self.tag_id] = values
            return self.renderlist('Dataset "%s" Tag "%s" Values' % (self.data_id, self.tag_id),
                                   [self.render.FileTagValBlock(file,
                                                                self.tagdef,
                                                                [self.tag_id])])

    def buildtaginfo(self, ownerwhere):
        owner = self.owner()
        where1 = ''
        if ownerwhere:
            where1 = 'owner %s' % ownerwhere
        filtered_tagdefs = self.select_tagdef(where=where1, order='tagname')
        
        tagdefs = [ tagdef for tagdef in filtered_tagdefs if (len(self.listtags)==0 or tagdef.tagname in self.listtags) ]
        for tagdef in tagdefs:
            tagdef.writeok = self.test_tag_authz('write', tagdef.tagname, fowner=owner)

        return tagdefs

    def GETtag(self, uri):
        # RESTful get of exactly one tag on one file...
        return self.dbtransact(self.get_tag_body, self.get_tag_postCommit)

    def get_all_body(self):
        predlist = []
        if self.data_id:
            predlist.append( dict(tag='name', op='=', vals=[self.data_id]) )
            
        self.txlog('GET ALL TAGS', dataset=self.data_id)

        custom_tags = self.getParamsDb('tag list tags', data_id=self.view_type)
        self.listtags = self.queryopts.get('list', set(custom_tags))
        if not self.listtags:
            self.listtags = set()
        if type(self.listtags) != set:
            self.listtags = set([self.listtags])

        all = self.globals['tagdefsdict'].values()
        if len(self.listtags) > 0:
            all = [ tagdef for tagdef in all if tagdef.tagname in self.listtags ]
        else:
            self.listtags = [ tagdef.tagname for tagdef in all ]
        all.sort(key=lambda tagdef: tagdef.tagname)
        system = [ tagdef for tagdef in all if tagdef.owner == None ]
        userdefined = [ tagdef for tagdef in all if tagdef.owner != None ]

        files = [ file for file in self.select_files_by_predlist(predlist, listtags=self.listtags) ]
        length = 0
        for file in files:
            for tagname in self.listtags:
                length = listOrStringMax(file[tagname], length)

        return (files, system, userdefined, all, length)

    def get_title_one(self):
        return 'Tags for dataset "%s"' % self.data_id

    def get_title_all(self):
        return 'Tags for all datasets'

    def get_all_html_render(self, results):
        files, system, userdefined, all, length = results
        #web.debug(system, userdefined, all)
        if self.data_id:
            return self.renderlist(self.get_title_one(),
                                   [self.render.FileTagExisting('User', files[0], userdefined),
                                    self.render.FileTagExisting('System', files[0], system),
                                    self.render.TagdefNewShortcut('Define more tags')])
        else:
            return self.renderlist(self.get_title_all(),
                                   [self.render.FileTagValExisting('', files, all)])

    def get_all_postCommit(self, results):
        files, system, userdefined, all, length = results

        if 'name' not in self.listtags:
            addName = True
        else:
            addName = False

        jsonMungeTags = set( [ tagdef.tagname for tagdef in all if tagdef.typestr in jsonMungeTypes ] )

        def dictFile(file):
            tagvals = [ ( tag, file[tag] ) for tag in self.listtags ]
            if addName:
                tagvals.append( ( 'name', file.file ) )
            tagvals = dict(tagvals)
            for tagname in jsonMungeTags:
                tagvals[tagname] = str(tagvals[tagname])
            return tagvals

        self.setNoCache()
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                return self.render.FileTagUriList(files, all)
            elif acceptType == 'application/x-www-form-urlencoded':
                web.header('Content-Type', 'application/x-www-form-urlencoded')
                body = []
                for file in files:
                    for tagdef in tagdefs:
                        if file[tagdef.tagname]:
                            if tagdef.typestr == '':
                                body.append(urlquote(tagdef.tagname))
                            elif tagdef.multivalue:
                                for val in file[tagdef.tagname]:
                                    body.append(urlquote(tagdef.tagname) + '=' + urlquote(val))
                            else:
                                body.append(urlquote(tagdef.tagname) + '=' + urlquote(file[tagdef.tagname]))
                return '&'.join(body)
            elif acceptType == 'application/json':
                return '[' + ",\n".join([ jsonWriter(dictFile(file)) for file in files ]) + ']\n'
            elif acceptType == 'text/html':
                break
        # render HTML result
        return self.get_all_html_render(results)
        
    def GETall(self, uri):
        # HTML get of all tags on one file...
        return self.dbtransact(self.get_all_body, self.get_all_postCommit)

    def GET(self, uri=None):
        # dispatch variants, browsing and REST
        self.globals['referer'] = self.home + uri
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
                predlist = [ { 'tag' : 'Dataset Name', 'op' : '=', 'vals' : [self.data_id] } ]
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
                if tag_id not in ['Image Set', 'contains' ]:
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
                tag = urlunquote(tag)
                val = urlunquote(val)

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
                predlist = [ { 'tag' : 'Dataset Name', 'op' : '=', 'vals' : [self.data_id] } ]
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
        #web.debug('post_nullBody')
        return None

    def post_postCommit(self, results):
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
                    self.tagvals[urlunquote(tag_id)] = [ value ]
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
                self.referer = '/tags/' + urlquote(self.data_id)
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
        self.globals['tagspace'] = 'tagdefacl'

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

    def get_all_body(self):
        """Override FileTags.get_all_body to consult tagdef ACL instead"""
        tagdefs = [ tagdef for tagdef in self.select_tagdef(self.data_id) ]
        if len(tagdefs) == 0:
            raise NotFound(data='tag definition "%s"' % self.data_id)

        acldefs = [ web.storage(tagname='readers', typestr='rolepat', multivalue=True),
                    web.storage(tagname='writers', typestr='rolepat', multivalue=True) ]

        length = 0
        for tagdef in tagdefs:
            tagdef.file = tagdef.tagname
            for acldef in acldefs:
                mode = dict(readers='read', writers='write')[acldef.tagname]
                aclvals = [ res.value for res in self.select_tag_acl(mode, tag_id=tagdef.tagname) ]
                length = max(length, listmax(aclvals))
                tagdef[dict(read='readers', write='writers')[mode]] = aclvals
                if tagdef.owner in self.authn.roles:
                    tagdef.writeok = True
                else:
                    tagdef.writeok = False

        return (tagdefs, [], [], acldefs, length)

    def get_title_one(self):
        return 'ACLs for tag "%s"' % self.data_id

    def get_title_all(self):
        return 'ACLs for all tags'

    def get_all_html_render(self, results):
        tagdefs, system, userdefined, all, length = results
        self.globals['tagdefsdict'] = dict([ (x.tagname, x) for x in all ])
        if self.data_id:
            return self.renderlist(self.get_title_one(),
                                   [self.render.FileTagExisting('', tagdefs[0], all)])
        else:
            return self.renderlist(self.get_title_all(),
                                   [self.render.FileTagValExisting('', tagdefs, all)])       

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
    def __init__(self, appname, queryopts={}, path=[]):
        Node.__init__(self, appname)
        self.path = path
        if len(self.path) == 0:
            self.path = [ ( [], [], [] ) ]
        self.predlist = self.path[-1][0]
        self.queryopts = queryopts
        self.action = 'query'
        self.globals['view'] = None

    def qtarget(self):
        qpath = []
        for elem in self.path:
            predlist, listtags, ordertags = elem
            terms = []
            for pred in predlist:
                if pred['op']:
                    terms.append(urlquote(pred['tag']) + pred['op'] + ",".join([ urlquote(val) for val in pred['vals'] ]))
                else:
                    terms.append(urlquote(pred['tag']))
            if not listtags or len(listtags) == 1 and listtags[0] == 'contains':
                listpart = ''
            else:
                listpart = '(' + ','.join([ urlquote(tag) for tag in listtags ]) + ')'
            qpath.append( ';'.join(terms) + listpart )
        return self.home + web.ctx.homepath + '/query/' + '/'.join(qpath)

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

        try:
            self.globals['view'] = self.queryopts['view']
        except:
            pass

        versions = self.queryopts.get('versions')
        if versions not in [ 'latest', 'any' ]:
            versions = 'latest'

        if versions == 'any':
            self.showversions = True
        else:
            self.showversions = False
                
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

        if self.action in [ 'add', 'delete' ]:
            # apply predlist changes to last path element
            predlist, listtags, ordertags = self.path[-1]
            self.path[-1] = (self.predlist, listtags, ordertags)

        self.globals['queryTarget'] = self.qtarget()
            
        def body():
            listtags = self.queryopts.get('list', self.path[-1][1])
            if len(listtags) == 0:
                listtags = self.getParamsDb('file list tags', data_id=self.globals['view'])
            listtags = [ t for t in listtags ]
            self.globals['filelisttags'] = listtags
            self.globals['filelisttagswrite'] = self.getParamsDb('file list tags write', data_id=self.globals['view'])
            predlist, listtags, ordertags = self.path[-1]
            self.path[-1] = predlist, list(self.globals['filelisttags']), ordertags
            self.path[-1][1].append('Image Set') # we always need this

            files = [ res for res in self.select_files_by_predlist_path(path=self.path, versions=versions) ]

            for res in files:
                # decorate each result with writeok information
                res.writeok = self.gui_test_file_authz('write',
                                                       owner=res.owner,
                                                       data_id=res.file,
                                                       local=res.local)
            return files

        def postCommit(files):
            listtags = self.globals['filelisttags']
            if 'name' not in listtags:
                addName = True
            else:
                addName = False

            jsonMungeTags = set( [ tagname for tagname in listtags
                                   if self.globals['tagdefsdict'][tagname].typestr in jsonMungeTypes ] )

            def jsonFile(file):
                tagvals = [ ( tag, file[tag] ) for tag in listtags ]
                if addName:
                    tagvals.append( ( 'name', file.file ) )
                tagvals = dict(tagvals)
                for tagname in jsonMungeTags:
                    tagvals[tagname] = str(tagvals[tagname])
                return jsonWriter(tagvals)

            self.setNoCache()

            if self.action in set(['add', 'delete']):
                raise web.seeother(self.globals['queryTarget'] + '?action=edit')

            if self.title == None:
                if self.action == 'query':
                    self.title = "Query Results"
                else:
                    self.title = "Query by Tags"

            if self.action == 'query':
                for acceptType in self.acceptTypesPreferedOrder():
                    if acceptType == 'text/uri-list':
                        # return raw results for REST client
                        yield self.render.FileUriList(files)
                        return
                    elif acceptType == 'application/json':
                        yield '['
                        if files:
                            yield jsonFile(files[0]) + '\n'
                        if len(files) > 1:
                            for file in files[1:]:
                                yield ',' + jsonFile(file) + '\n'
                        yield ']\n'
                        return
                    elif acceptType == 'text/html':
                        break
                yield self.renderlist(self.title,
                                       [self.render.QueryViewStatic(self.ops, self.predlist),
                                        self.render.FileList(files, showversions=self.showversions)])
            else:
                yield self.renderlist(self.title,
                                       [self.render.QueryAdd(self.ops),
                                        self.render.QueryView(self.ops, self.predlist),
                                        self.render.FileList(files, showversions=self.showversions)])

        for res in self.dbtransact(body, postCommit):
            yield res


