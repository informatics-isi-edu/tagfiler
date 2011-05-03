
# 
# Copyright 2010 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# define abstract syntax tree nodes for more readable code
import traceback
import sys
import web
import urllib
import re
import os
import webauthn
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote, urlunquote, idquote, jsonWriter, parseBoolString, predlist_linearize, path_linearize
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

class Subquery:
    """Stub AST node holds a query path that is not wrapped in a full URI.

       This class cannot be invoked by the URL dispatcher as it has no web methods."""
    def __init__(self, path):
        self.path = path
        self.is_subquery = True

    def __repr__(self):
        return "@(%s)" % path_linearize(self.path)

class Node (object, Application):
    """Abstract AST node for all URI patterns"""

    __slots__ = [ 'appname' ]

    def __init__(self, parser, appname):
        self.appname = appname
        Application.__init__(self, parser)

    def uri2referer(self, uri):
        return self.config['home'] + uri

class TransmitNumber (Node):
    """Represents a transmitnumber URI

       POST tagfiler/transmitnumber
    """

    __slots__ = []

    def __init__(self, parser, appname):
        Node.__init__(self, parser, appname)

    def POST(self, uri):

        def body():
            if self.table == 'transmitnumber':
                result  = self.select_next_transmit_number()
            elif self.table == 'keygenerator':
                result  = self.select_next_key_number()
            else:
                result = ''
                
            return result

        def postCommit(results):
            uri = self.config['home'] + '/transmitnumber/' + results
            web.header('Location', results)
            return results

        self.storage = web.input()
        
        try:
            self.table = urllib.unquote_plus(self.storage.table)
        except:
            pass
        
        return self.dbtransact(body, postCommit)

class Study (Node):
    """Represents a study URI

       GET tagfiler/study?action=upload
    """

    __slots__ = []

    def __init__(self, parser, appname, subjpreds=[], queryopts={}):
        Node.__init__(self, parser, appname)
        self.action = 'get'
        self.study_type = None
        self.study_size = None
        self.count = None
        self.status = None
        self.direction = 'upload'
        self.subjpreds = subjpreds
        self.name = ''.join([ ''.join(res.vals) for res in self.subjpreds if res.tag == 'name' and res.op == '='] )
        if len(self.name) == 0:
            self.name = None
        self.version = ''.join([ ''.join(res.vals) for res in self.subjpreds if res.tag == 'version' and res.op == '='] )
        if len(self.version) == 0:
            self.version = None

    def GET(self, uri):
        try:
            self.action = urllib.unquote_plus(self.storage.action)
        except:
            pass

        try:
            self.study_type = urllib.unquote_plus(self.storage.type)
        except:
            pass

        try:
            self.direction = urllib.unquote_plus(self.storage.direction)
        except:
            pass

        try:
            self.status = urllib.unquote_plus(self.storage.status)
        except:
            pass

        def body():
            files = []

            config = self.select_config(self.study_type, [ ('applet tags', []), ('applet tags require', []) ])
            self.globals['appletTagnames'] = config['applet tags']
            self.globals['appletTagnamesRequire'] = config['applet tags require']
            
            if self.action == 'get' and self.subjpreds:
                self.unique = self.validate_subjpreds_unique(acceptName=True)
                
                if self.unique:
                    versions = 'any'
                else:
                    versions = 'latest'
                
                results = self.select_files_by_predlist(self.subjpreds,
                                                        listtags=['vcontains', 'id'] + [ tagname for tagname in self.globals['appletTagnames']],
                                                        versions=versions)
                if len(results) == 0:
                    if not self.status:
                        raise NotFound('study "%s@%s"' % (self.name, self.version))
                else:
                    self.subject = results[0]
                    self.datapred, self.dataid, self.dataname, self.subject.dtype = self.subject2identifiers(self.subject)
                    files = self.subject.vcontains
                    if not files:
                        files = []
    
                self.globals['appletTagvals'] = [ (tagname,
                                                   [ subject.tagname ])
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
                self.globals['version'] = self.version
                return self.renderlist("Study Download",
                                       [self.render.TreeDownload(self.name)])
            elif self.action == 'get':
                success = None
                error = None
                if self.status == 'success':
                    success = 'All files were successfully %sed.' % self.direction
                elif self.status == 'error':
                    error = 'An unknown error prevented a complete %s.' % self.direction
                else:
                    error = self.status
    
                if self.name:
                    self.globals['version'] = self.version
                    return self.renderlist(None,
                                           [self.render.TreeStatus(self.name, self.direction, success, error, files)])
                else:
                    url = '/appleterror'
                    if self.status:
                        url += '?status=%s' % urlquote(self.status)
                    raise web.seeother(url)
            else:
                raise BadRequest('Unrecognized action form field.')

        return self.dbtransact(body, postCommit)

    def PUT(self, uri):
        self.storage = web.input()
        try:
            self.study_size = int(urllib.unquote_plus(self.storage.study_size))
        except:
            pass

        try:
            self.count = int(urllib.unquote_plus(self.storage.count))
        except:
            pass

        try:
            self.status = urllib.unquote_plus(self.storage.status)
        except:
            pass

        try:
            self.direction = urllib.unquote_plus(self.storage.direction)
        except:
            pass

        try:
            self.key = urllib.unquote_plus(self.storage.key)
        except:
            pass

        def body():
            result = True
            if self.direction == 'upload' and self.status == 'success':
                results = self.select_dataset_size(self.key)[0]
                if results.size != self.study_size or results.count != self.count:
                    self.status = 'conflict'
                    result = None
            if self.status == 'success':
                self.txlog('STUDY %s OK REPORT' % self.direction.upper(), dataset=self.name)
            else:
                self.txlog('STUDY %s FAILURE REPORT' % self.direction.upper(), dataset=self.name)
            return result

        def postCommit(result):
            if not result:
                raise Conflict('The size of the uploaded dataset "%s" does not match original file(s) size.' % (self.name))

        return self.dbtransact(body, postCommit)

class AppletError (Node):
    """Represents an appleterror URI

       GET tagfiler/appleterror?status=string
    """

    __slots__ = []

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname)
        self.action = None
        self.status = None

    def GET(self, uri):
        try:
            self.status = urllib.unquote_plus(self.storage.status)
        except:
            pass

        # the applet needs to manage expiration itself
        # since it may be active while the html page is idle
        target = self.config['home'] + web.ctx.homepath
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

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname)
        self.globals['view'] = None
        self.queryopts = queryopts

    def GET(self, uri):
        
        web.header('Content-Type', 'text/html;charset=ISO-8859-1')
        self.globals['referer'] = self.config['home'] + uri
        self.storage = web.input()

        def body():
            tagdefs = [ (tagdef.tagname, tagdef)
                        for tagdef in self.select_tagdef() ]

            listtags = self.queryopts.get('list', None)
            writetags = None
            if not listtags:
                view = self.select_view(self.globals['view'])
                listtags = view['file list tags']
                writetags = view['file list tags write']

            builtinlist = [ 'id' ]
            self.globals['filelisttags'] = builtinlist + [ tag for tag in listtags if tag not in builtinlist ]
            self.globals['filelisttagswrite'] = writetags
            
            if self.globals['tagdefsdict'].has_key('list on homepage'):
                self.subjpreds = [ web.Storage(tag='list on homepage', op=None, vals=[]) ]
                self.homepage = True
            else:
                self.subjpreds=[]
                self.homepage = False

            if self.globals['tagdefsdict'].has_key('homepage order'):
                ordertags = ['homepage order']
            else:
                ordertags = []

            return self.select_files_by_predlist(listtags=set(self.globals['filelisttags']).union(set(['Image Set', 'id',
                                                                                                       'name', 'version',
                                                                                                       'tagdef', 'typedef',
                                                                                                       'config', 'view', 'url'])),
                                                 ordertags=ordertags)

        def postCommit(files):
            target = self.config['home'] + web.ctx.homepath
            self.setNoCache()
            if self.homepage:
                return self.renderlist(None,
                                       [self.render.Homepage(files)])
            else:
                return self.renderlist(None,
                                       [self.render.Commands(),
                                        self.render.FileList(files)])
                
        action = None
        name = None
        filetype = None
        readers = None
        writers = None
        try:
            action = urllib.unquote_plus(self.storage.action)
            try:
                name = urllib.unquote_plus(self.storage.name)
                filetype = urllib.unquote_plus(self.storage.type)
                readers = urllib.unquote_plus(self.storage['read users'])
                writers = urllib.unquote_plus(self.storage['write users'])
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
                if filetype not in [ 'file', 'url', 'dataset' ]:
                    filetype = 'file'

                url = self.config['home'] + web.ctx.homepath + '/file/name=' + urlquote(name)
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
                self.globals['view'] = urllib.unquote_plus(self.storage.view)
            except:
                pass
            return self.dbtransact(body, postCommit)

    def POST(self, uri):
        storage = web.input()
        name = None
        url = None
        dtype = None
        try:
            action = storage.action
            
            try:
                name = storage.name
            except:
                pass
            
            try:
                url = storage.url
                dtype = 'url'
            except:
                pass
        except:
            raise BadRequest('Expected action form field.')
        subjpreds = []
        storage=dict([(k, urlquote(v)) for k, v in storage.items()])
        if storage['action'] == 'define':
            if name:
                subjpreds.append( web.Storage(tag='name', op='=', vals=[name]) )
            storage.action = 'post'
        if subjpreds:
            path = [ ( subjpreds, [], [] ) ]
        else:
            path = []
        ast = FileId(appname=self.appname,
                     parser=self.url_parse_func,
                     path=path,
                     url=url,
                     dtype=dtype,
                     queryopts=self.queryopts,
                     storage=storage)
        ast.preDispatchFake(uri, self)
        return ast.POST(uri)

class LogList (Node):
    """Represents a bare LOG/ URI

       GET LOG or LOG/  -- gives a listing
       """

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname)

    def GET(self, uri):
        if not self.authn.hasRoles(['admin']):
            raise Forbidden('listing of log files')
        
        if self.config['log path']:
            lognames = sorted(os.listdir(self.config['log path']), reverse=True)
                              
        else:
            lognames = []
        
        target = self.config['home'] + web.ctx.homepath
        
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

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname)

    def GET(self, uri):
        
        self.setNoCache()
        return self.renderlist("Contact Us",
                               [self.render.Contact()])

class FileId(Node, FileIO):
    """Represents a direct FILE/subjpreds URI

       Just creates filename and lets FileIO do the work.

    """
    __slots__ = [ 'storagename', 'dtype', 'queryopts' ]
    def __init__(self, parser, appname, path, file=None, dtype='url', queryopts={}, versions='any', url=None, storage=None):
        Node.__init__(self, parser, appname)
        FileIO.__init__(self)
        self.path = [ ( e[0], e[1], [] ) for e in path ]
        self.file = file
        self.dtype = dtype
        self.url = url
        self.queryopts = queryopts
        self.versions = versions
        if storage:
            self.storage = storage

class LogId(Node, LogFileIO):
    """Represents a direct LOG/subjpreds URI

       Just creates filename and lets LogFileIO do the work.

    """
    __slots__ = [ ]
    def __init__(self, parser, appname, name, queryopts={}):
        Node.__init__(self, parser, appname)
        LogFileIO.__init__(self)
        self.name = name
        self.queryopts = queryopts

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

    __slots__ = [ 'tag_id', 'typestr', 'target', 'action', 'tagdefs', 'writepolicy', 'readpolicy', 'multivalue', 'queryopts' ]

    def __init__(self, parser, appname, tag_id=None, typestr=None, queryopts={}):
        Node.__init__(self, parser, appname)
        self.tag_id = tag_id
        self.typestr = typestr
        self.writepolicy = None
        self.readpolicy = None
        self.multivalue = None
        self.is_unique = None
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
            predefined = [ tagdef for tagdef in self.select_tagdef(subjpreds=[web.Storage(tag='owner', op=':not:', vals=[])], order='tagdef') ]
            userdefined = [ tagdef for tagdef in self.select_tagdef(subjpreds=[web.Storage(tag='owner', op=None, vals=[])], order='tagdef') ]
            types = self.get_type()
            
            return (predefined, userdefined, types)

        def postCommit(defs):
            web.header('Content-Type', 'text/html;charset=ISO-8859-1')
            self.setNoCache()
            predefined, userdefined, types = defs
            test_tagdef_authz = lambda mode, tag: self.test_tagdef_authz(mode, tag)
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting('User', userdefined),
                                    self.render.TagdefExisting('System', predefined )])

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
            tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
            if tagdef == None:
                raise NotFound(data='tag definition %s' % (self.tag_id))
            self.enforce_tagdef_authz('write', tagdef)
            self.delete_tagdef(tagdef)
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
                self.typestr = 'empty'

        if self.readpolicy == None:
            try:
                self.readpolicy = self.queryopts['readpolicy'].lower()
            except:
                self.readpolicy = 'subjectowner'

        if self.writepolicy == None:
            try:
                self.writepolicy = self.queryopts['writepolicy'].lower()
            except:
                self.writepolicy = 'subjectowner'

        if self.multivalue == None:
            try:
                multivalue = self.queryopts['multivalue'].lower()
            except:
                multivalue = 'false'
            if multivalue in [ 'true', 't', 'yes', 'y' ]:
                self.multivalue = True
            else:
                self.multivalue = False

        if self.is_unique == None:
            try:
                unique = self.queryopts['unique'].lower()
            except:
                unique = 'false'
            if unique in [ 'true', 't', 'yes', 'y' ]:
                self.is_unique = True
            else:
                self.is_unique = False

        def body():
            if len( set(self.config['tagdef write users']).intersection(set(self.authn.roles).union(set('*'))) ) == 0:
                raise Forbidden('creation of tag definitions')
                
            results = self.select_tagdef(self.tag_id, enforce_read_authz=False)
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
                        try:
                            unique = storage['unique-%s' % (key[4:])]
                        except:
                            unique = False
                        self.tagdefs[storage[key]] = (typestr, readpolicy, writepolicy, parseBoolString(multivalue), parseBoolString(unique))
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
                if len( set(self.config['tagdef write users']).intersection(set(self.authn.roles).union(set('*'))) ) == 0:
                    raise Forbidden('creation of tag definitions')
                
                for tagname in self.tagdefs.keys():
                    self.tag_id = tagname
                    self.typestr, self.readpolicy, self.writepolicy, self.multivalue, self.is_unique = self.tagdefs[tagname]
                    results = self.select_tagdef(self.tag_id, enforce_read_authz=False)
                    if len(results) > 0:
                        raise Conflict(data="Tag %s is already defined." % self.tag_id)
                    self.insert_tagdef()
                    self.log('CREATE', tag=self.tag_id)
            elif self.action == 'delete' or self.action == 'CancelDelete':
                tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
                if tagdef == None:
                    raise NotFound('tag definition "%s"' % self.tag_id)
                self.globals['dataname'] = self.tag_id
                self.globals['datapred'] = urlquote(self.tag_id)
                self.enforce_tagdef_authz('write', tagdef)
                return None
            elif self.action == 'ConfirmDelete':
                tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
                if tagdef == None:
                    raise NotFound('tag definition "%s"' % self.tag_id)
                self.enforce_tagdef_authz('write', tagdef)
                self.delete_tagdef(tagdef)
                self.log('DELETE', tag=self.tag_id)
            else:
                raise BadRequest(data="Form field action=%s not understood." % self.action)
            return None

        def postCommit(results):
            if self.action == 'delete':
                self.globals['name'] = self.tag_id
                self.globals['version'] = None
                return self.renderlist("Delete Confirmation",
                                       [self.render.ConfirmForm('tagdef')])
            else:
                # send client back to get form page again
                raise web.seeother('/tagdef')

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/subjpreds and TAGS/subjpreds/tagvals URIs"""

    __slots__ = [ 'tag_id', 'value', 'tagvals' ]

    def __init__(self, parser, appname, path=None, queryopts={}):
        Node.__init__(self, parser, appname)
        if path:
            self.path = path
        else:
            self.path = [ ([], [], []) ]
        self.referer = None
        self.queryopts = queryopts
        self.globals['queryTarget'] = self.qtarget()
        self.globals['queryAllTags'] = self.qAllTags()

    def qAllTags(self):
        if self.queryopts.get('view') == 'default':
            return None

        url = self.config['home'] + web.ctx.homepath + '/tags' + path_linearize(self.path)
        opts = '&'.join([ '%s=%s' % (urlquote(k), urlquote(v)) for k, v in self.queryopts.items() if k != 'view' ])
        url += '?view=default'
        if opts:
            url += opts
        return url

    def qtarget(self):
        if self.queryopts.get('view') == 'default':
            return None

        url = self.config['home'] + web.ctx.homepath + '/tags/' + path_linearize(self.path)
        opts = '&'.join([ '%s=%s' % (urlquote(k), urlquote(v)) for k, v in self.queryopts.items() ])
        if opts:
            url += '?' + opts
        return url

    def get_body(self):

        self.path_modified, self.listtags, writetags, self.limit, self.versions = \
              self.prepare_path_query(self.path,
                                      list_priority=['path', 'list', 'view', 'all'],
                                      list_prefix='tag',
                                      extra_tags=
                                      [ 'id', 'file', 'name', 'version', 'Image Set',
                                        'write users', 'modified' ] 
                                      + [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique ])

        self.txlog('GET TAGS', dataset=path_linearize(self.path_modified))
        
        if len(self.listtags) == len(self.globals['tagdefsdict'].values()) and self.queryopts.get('view') != 'default':
            try_default_view = True
        else:
            try_default_view = False
            
        all = [ tagdef for tagdef in self.globals['tagdefsdict'].values() if tagdef.tagname in self.listtags ]
        all.sort(key=lambda tagdef: tagdef.tagname)

        files = [ file for file in self.select_files_by_predlist_path(self.path_modified, versions=self.versions, limit=self.limit)  ]
        if len(files) == 0:
            raise NotFound('subject matching "%s"' % predlist_linearize(self.path_modified[-1][0]))
        elif len(files) == 1:
            subject = files[0]
            datapred, dataid, dataname, subject.dtype = self.subject2identifiers(subject)

            if try_default_view and subject.dtype:
                view = self.select_view(subject.dtype)
                if view and view['tag list tags']:
                    self.listtags = view['tag list tags']

        length = 0
        for file in files:
            for tagname in self.listtags:
                length = listOrStringMax(file[tagname], length)

        return (files, all, length)

    def get_postCommit(self, results):
        files, all, length = results

        jsonMungeTags = set( [ tagdef.tagname for tagdef in all if tagdef.typestr in jsonMungeTypes ] )

        def dictFile(file):
            tagvals = [ ( tag, file[tag] ) for tag in self.listtags ]
            tagvals = dict(tagvals)
            for tagname in jsonMungeTags:
                tagvals[tagname] = str(tagvals[tagname])
            return tagvals

        self.setNoCache()
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                web.header('Content-Type', 'text/uri-list')
                self.globals['str'] = str 
                return self.render.FileTagUriList(files, all)
            elif acceptType == 'application/x-www-form-urlencoded' and len(files) == 1:
                web.header('Content-Type', 'application/x-www-form-urlencoded')
                body = []
                file = files[0]
                for tagdef in all:
                    if file[tagdef.tagname]:
                        if tagdef.typestr == 'empty':
                            body.append(urlquote(tagdef.tagname))
                        elif tagdef.multivalue:
                            for val in file[tagdef.tagname]:
                                body.append(urlquote(tagdef.tagname) + '=' + urlquote(val))
                        else:
                            body.append(urlquote(tagdef.tagname) + '=' + urlquote(file[tagdef.tagname]))
                return '&'.join(body)
            elif acceptType == 'application/json':
                web.header('Content-Type', 'application/json')
                return '[' + ",\n".join([ jsonWriter(dictFile(file)) for file in files ]) + ']\n'
            elif acceptType == 'text/plain' and len(files) == 1:
                web.header('Content-Type', 'text/plain')
                return '\n'.join(values) + '\n'
            elif acceptType == 'text/html':
                break
                
        # render HTML result
        if self.queryopts.get('values', None) == 'basic':
            self.globals['smartTagValues'] = False

        simplepath = [ x for x in self.path ]
        simplepath[-1] = simplepath[-1][0], [], []

        tagdefs = [ x for x in all if x.tagname in self.listtags ]
            
        if len(files) == 1:
            return self.renderlist('Tag(s) for subject matching "%s"' % urllib.unquote_plus(path_linearize(simplepath)),
                                   [self.render.FileTagExisting('', files[0], tagdefs)])
        else:
            return self.renderlist('Tag(s) for subjects matching "%s"' % urllib.unquote_plus(path_linearize(simplepath)),
                                   [self.render.FileTagValExisting('', files, tagdefs)])

    def GET(self, uri=None):
        # dispatch variants, browsing and REST
        self.globals['referer'] = self.config['home'] + uri
        try:
            self.view_type = urllib.unquote_plus(self.storage.view)
        except:
            pass

        return self.dbtransact(self.get_body, self.get_postCommit)

    def put_body(self):
        subjpreds, listpreds, ordertags = self.path[-1]
        
        unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True, subjpreds=subjpreds)
        if unique == False:
            versions = 'latest'
        else:
            versions = 'any'

        self.tagvals = dict()
        for pred in listpreds:
            if pred.op and pred.op != '=':
                raise BadRequest('Invalid operation "%s" for tag binding in PUT.' % pred.op)
            if self.tagvals.has_key(pred.tag):
                raise BadRequest('Tag "%s" occurs in more than one binding predicate in PUT.' % pred.tag)
            self.tagvals[pred.tag] = pred.vals
        
        listpreds =  subjpreds + [ web.Storage(tag=tag,op=None,vals=[]) for tag in ['id', 'owner', 'write users', 'Image Set', 'url', 'incomplete'] ]

        simplepath = [ x for x in self.path ]
        simplepath[-1] = ( simplepath[-1][0], [], [] )

        self.path_modified = [ x for x in self.path ]
        self.path_modified[-1] = (subjpreds, listpreds, ordertags)
        
        results = self.select_files_by_predlist_path(self.path_modified, versions=versions)
        if len(results) == 0:
            raise NotFound(data='subject matching "%s"' % path_linearize(simplepath))
        elif len(results) > 1:
            raise Conflict('PUT tags to more than one subject is not supported.')

        self.subject = results[0]
        self.id = self.subject.id

        # custom DEI EIU hack, proxy tag ops on Image Set to all member files
        if self.subject['Image Set']:
            path = [ ( [ web.Storage(tag='id', op='=', vals=[self.id]) ], [web.Storage(tag='vcontains',op=None,vals=[])], [] ),
                     ( [], [], [] ) ]
            subfiles = self.select_files_by_predlist_path(path=path)
        else:
            subfiles = []

        for tag_id in self.tagvals.keys():
            tagdef = self.globals['tagdefsdict'].get(tag_id, None)
            if tagdef == None:
                raise NotFound(data='tag definition "%s"' % tag_id)
            self.enforce_tag_authz('write', self.subject, tagdef)
            self.txlog('SET', dataset=self.subject2identifiers(self.subject)[0], tag=tag_id, value=','.join(['%s' % val for val in self.tagvals[tag_id]]))
            if self.tagvals[tag_id]:
                for value in self.tagvals[tag_id]:
                    self.set_tag(self.subject, tagdef, value)
                    if tag_id not in ['Image Set', 'contains', 'vcontains', 'list on homepage', 'key', 'check point offset' ] and not tagdef.unique:
                        for subfile in subfiles:
                            self.enforce_tag_authz('write', subfile, tagdef)
                            self.txlog('SET', dataset=self.subject2identifiers(subfile)[0], tag=tag_id, value=value)
                            self.set_tag(subfile, tagdef, value)
            else:
                self.set_tag(self.subject, tagdef)
                if tag_id not in ['Image Set', 'contains', 'vcontains', 'list on homepage', 'key', 'check point offset' ] and not tagdef.unique:
                    for subfile in subfiles:
                        self.enforce_tag_authz('write', subfile, tagdef)
                        self.txlog('SET', dataset=self.subject2identifiers(subfile)[0], tag=tag_id)
                        self.set_tag(subfile, tagdef)

        if not self.referer:
            # set updated referer based on updated subject, unless client provided a referer
            self.referer = '/tags/' + self.subject2identifiers(self.subject)[0]
            
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
            tagvals = dict()
            for tagval in content.strip().split('&'):
                tag, val = tagval.split('=')
                tag = urlunquote(tag)
                val = urlunquote(val)

                if tag == '':
                    raise BadRequest(data="A non-empty tag name is required.")

                try:
                    vals = tagvals[tag]
                except:
                    tagvals[tag] = []
                    vals = tagvals[tag]
                vals.append(val)

            subjpreds, listpreds, ordertags = self.path[-1]
            for tag, vals in tagvals.items():
                listpreds.append( web.Storage(tag=tag,op='=', vals=vals) )
        return self.dbtransact(self.put_body, self.put_postCommit)

    def delete_body(self, previewOnly=False):
        subjpreds, origlistpreds, ordertags = self.path[-1]
        
        unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True, subjpreds=subjpreds)
        if unique == False:
            versions = 'latest'
        else:
            # unique is True or None
            versions = 'any'

        listpreds =  [ web.Storage(tag=tag,op=None,vals=[]) for tag in ['id', 'Image Set', 'view', 'name', 'version', 'incomplete'] ] + origlistpreds

        simplepath = [ x for x in self.path ]
        simplepath[-1] = ( simplepath[-1][0], [], [] )

        self.path_modified = [ x for x in self.path ]
        self.path_modified[-1] = (subjpreds, listpreds, ordertags)
         
        results = self.select_files_by_predlist_path(self.path_modified, versions=versions)
        if len(results) == 0:
            raise NotFound(data='subject matching "%s"' % path_linearize(simplepath))
        self.subjects = [ res for res in results ]

        # find subfiles of all subjects which are tagged Image Set
        path = [ ( self.subjpreds + [ web.Storage(tag='Image Set', op='', vals=[]) ], [web.Storage(tag='vcontains',op=None,vals=[])], [] ),
                 ( [], [web.Storage(tag='id',op=None,vals=[])], [] ) ]
        self.subfiles = dict([ (res.id, res) for res in self.select_files_by_predlist_path(path=path) ])

        for tag in set([pred.tag for pred in origlistpreds ]):
            tagdef = self.globals['tagdefsdict'].get(tag, None)
            if tagdef == None:
                raise NotFound('tagdef="%s"' % tag)

            if not previewOnly:
                for subject in self.subjects:
                    if tagdef.typestr == 'empty' or not subject[tag]:
                        vals = [None]
                    elif tagdef.multivalue:
                        vals = subject[tag]
                    else:
                        vals = [subject[tag]]
                    self.enforce_tag_authz('write', subject, tagdef)
                    self.txlog('DELETE', dataset=self.subject2identifiers(subject)[0], tag=tag, value=((vals[0]!=None) and ','.join([str(val) for val in vals])) or None)
                    for val in vals:
                        self.delete_tag(subject, tagdef, val)
            
                    if tag in [ 'read users', 'write users' ]:
                        for subfile in self.subfiles.values():
                            self.enforce_tag_authz('write', subfile, tagdef)
                            self.txlog('DELETE', dataset=self.subject2identifiers(subfile)[0], tag=tag, value=((vals[0]!=None) and ','.join([str(val) for val in vals])) or None)
                            for val in vals:
                                self.delete_tag(subfile, tagdef, val)

        if not previewOnly and not self.referer:
            if len(self.subjects) == 1:
                # set updated referer based on single match
                self.referer = '/tags/' + self.subject2identifiers(self.subjects[0])[0]
            else:
                # for multi-subject results, redirect to subjpreds, which may no longer work but never happens in GUI
                self.referer = '/tags/' + path_linearize(simplepath)
            
        return None

    def delete_postCommit(self, results):
        return ''

    def DELETE(self, uri):
        # RESTful delete of exactly one tag on 1 or more files...
        return self.dbtransact(self.delete_body, self.delete_postCommit)

    def post_postCommit(self, results):
        raise web.seeother(self.referer)

    def POST(self, uri):
        # simulate RESTful actions and provide helpful web pages to browsers
        storage = web.input()

        subjpreds, listpreds, ordertags = self.path[-1]
        listpreds = [ x for x in listpreds ]
        
        try:
            action = storage.action
            tagvals = dict()
            for key in storage.keys():
                if key[0:4] == 'set-':
                    tag_id = key[4:]
                    try:
                        vals = [ storage['val-%s' % (tag_id)] ]
                    except:
                        vals = []
                    tagvals[urlunquote(tag_id)] = vals
                elif key == 'tag':
                    try:
                        vals = [ storage.value ]
                    except:
                        vals = []
                    tagvals[storage.tag] = vals
                    
            for tag, vals in tagvals.items():
                listpreds.append( web.Storage(tag=tag, op='=', vals=vals) )
            try:
                self.referer = storage.referer
            except:
                self.referer = None
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception during filetags form post parsing',
                      traceback.format_exception(et, ev, tb))
            raise BadRequest(data="Error extracting form data.")

        self.path[-1] = (subjpreds, listpreds, ordertags)

        if action == 'put':
            return self.dbtransact(self.put_body, self.post_postCommit)
        elif action == 'delete':
            return self.dbtransact(self.delete_body, self.post_postCommit)
        else:
            raise BadRequest(data="Form field action=%s not understood." % action)

class Query (Node):
    __slots__ = [ 'subjpreds', 'queryopts', 'action' ]
    def __init__(self, parser, appname, queryopts={}, path=[]):
        Node.__init__(self, parser, appname)
        self.path = path
        if len(self.path) == 0:
            self.path = [ ( [], [], [] ) ]
        self.subjpreds = self.path[-1][0]
        self.queryopts = queryopts
        self.action = 'query'
        self.globals['view'] = None

    def qtarget(self):
        qpath = []
        for elem in self.path:
            subjpreds, listpreds, ordertags = elem
            #web.debug(listpreds)
            if listpreds:
                if len(listpreds) == 1 and listpreds[0].tag in [ 'contains', 'vcontains' ] and listpreds[0].op == None:
                    listpart = ''
                else:
                    listpart = '(%s)' % predlist_linearize(listpreds)
            else:
                listpart = ''

            qpath.append( predlist_linearize(subjpreds) + listpart )
        return self.config['home'] + web.ctx.homepath + '/query/' + '/'.join(qpath)

    def GET(self, uri):
        # this interface has both REST and form-based functions
        
        # test if user predicate equals a predicate from subjpreds
        def equals(pred, userpred):
            return ({'tag' : pred.tag, 'op' : pred.op, 'vals' : str(pred.vals)} == userpred)

        tagname = None
        op = None
        value = []
        try:
            self.action = self.queryopts['action']
            tagname = self.queryopts.tag
            op = self.queryopts.op
            if self.action == 'add':
                for i in range(0,10):
                    val = self.queryopts['val' + str(i)]
                    if val != None:
                        value.append(val)
            elif self.action == 'delete':
                value = self.queryopts.vals
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

        if op == '':
            op = None

        if op == None and self.action == 'delete':
            value = str([])

        userpred = web.Storage(tag=tagname, op=op, vals=value)

        if self.action == 'add':
            if userpred not in self.subjpreds:
                self.subjpreds.append( userpred )
        elif self.action == 'delete':
            self.subjpreds = [ pred for pred in self.subjpreds if not equals(pred, userpred) ]
        elif self.action == 'query':
            pass
        elif self.action == 'edit':
            pass
        else:
            raise BadRequest(data="Form field action=%s not understood." % self.action)

        if self.action in [ 'add', 'delete' ]:
            # apply subjpreds changes to last path element
            subjpreds, listtags, ordertags = self.path[-1]
            self.path[-1] = (self.subjpreds, listtags, ordertags)

        def body():

            path, self.listtags, writetags, self.limit, self.versions = \
                  self.prepare_path_query(self.path,
                                          list_priority=['path', 'list', 'view', 'default'],
                                          list_prefix='file',
                                          extra_tags=[ 'id', 'file','name', 'version','Image Set',
                                                       'write users', 'modified', 'url' ]
                                          + [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique ])

            self.globals['filelisttags'] = [ 'id' ] + [x for x in self.listtags if x !='id']
            self.globals['filelisttagswrite'] = writetags

            return self.select_files_by_predlist_path(path=path, versions=self.versions, limit=self.limit)

        def postCommit(files):
            if self.versions == 'any':
                self.showversions = True
            else:
                self.showversions = False
            
            self.globals['showVersions'] = self.showversions
            self.globals['queryTarget'] = self.qtarget()
                
            jsonMungeTags = set( [ tagname for tagname in self.globals['filelisttags']
                                   if self.globals['tagdefsdict'][tagname].typestr in jsonMungeTypes ] )

            def jsonFile(file):
                tagvals = [ ( tag, file[tag] ) for tag in self.listtags ]
                tagvals = dict(tagvals)
                for tagname in jsonMungeTags:
                    tagvals[tagname] = str(tagvals[tagname])
                return jsonWriter(tagvals)

            self.setNoCache()

            if self.action in set(['add', 'delete']):
                raise web.seeother(self.globals['queryTarget'] + '?action=edit&versions=%s' % self.versions )

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
                        if len(files) > 0:
                            yield jsonFile(files[0]) + '\n'
                        if len(files) > 1:
                            for i in range(1,len(files)):
                                yield ',' + jsonFile(files[i]) + '\n'
                        yield ']\n'
                        return
                    elif acceptType == 'text/html':
                        break
                yield self.renderlist(self.title,
                                       [self.render.QueryViewStatic(self.ops, self.subjpreds),
                                        self.render.FileList(files, showversions=self.showversions, limit=self.limit)])
            else:
                yield self.renderlist(self.title,
                                       [self.render.QueryAdd(self.ops, self.opsExcludeTypes),
                                        self.render.QueryView(self.ops, self.subjpreds),
                                        self.render.FileList(files, showversions=self.showversions, limit=self.limit)])

        for res in self.dbtransact(body, postCommit):
            yield res


