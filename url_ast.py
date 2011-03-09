

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
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote, urlunquote, idquote, jsonWriter, parseBoolString, predlist_linearize
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
        return self.config['home'] + uri

class TransmitNumber (Node):
    """Represents a transmitnumber URI

       POST tagfiler/transmitnumber
    """

    __slots__ = []

    def __init__(self, appname):
        Node.__init__(self, appname)

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

    def __init__(self, appname, name=None, queryopts={}):
        Node.__init__(self, appname)
        self.action = 'get'
        self.study_type = None
        self.study_size = None
        self.count = None
        self.status = None
        self.direction = 'upload'
        if type(name) == web.utils.Storage:
            self.name = name.name
            self.version = name.version
        else:
            self.name = name
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
            
            if self.action == 'get' and self.name:
                subjpreds = [ web.Storage(tag='name', op='=', vals=[self.name]) ]
                versions = 'latest'
                if self.version:
                    subjpreds.append( web.Storage(tag='version', op='=', vals=[self.version]) )
                    versions = 'any'
                
                results = self.select_files_by_predlist(subjpreds,
                                                        listtags=['vcontains'] + [ tagname for tagname in self.globals['appletTagnames']],
                                                        versions=versions)
                if len(results) == 0:
                    if not self.status:
                        raise NotFound('study "%s@%s"' % (self.name, self.version))
                else:
                    files = results[0].vcontains
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

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)
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

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)
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

            return self.select_files_by_predlist(listtags=set(self.globals['filelisttags']).union(set(['Image Set',
                                                                                                       'name', 'version',
                                                                                                       'tagdef', 'typedef',
                                                                                                       'config', 'view'])),
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
        ast = FileId(appname=self.appname,
                     subjpreds=subjpreds,
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

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)

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

    def __init__(self, appname, queryopts={}):
        Node.__init__(self, appname)

    def GET(self, uri):
        
        self.setNoCache()
        return self.renderlist("Contact Us",
                               [self.render.Contact()])

class FileId(Node, FileIO):
    """Represents a direct FILE/subjpreds URI

       Just creates filename and lets FileIO do the work.

    """
    __slots__ = [ 'storagename', 'dtype', 'queryopts' ]
    def __init__(self, appname, subjpreds, file=None, dtype='url', queryopts={}, versions='any', url=None, storage=None):
        Node.__init__(self, appname)
        FileIO.__init__(self)
        self.subjpreds = subjpreds
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
    def __init__(self, appname, name, queryopts={}):
        Node.__init__(self, appname)
        LogFileIO.__init__(self)
        self.name = name
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
                        self.tagdefs[storage[key]] = (typestr, readpolicy, writepolicy, parseBoolString(multivalue))
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
                    self.typestr, self.readpolicy, self.writepolicy, self.multivalue = self.tagdefs[tagname]
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

    def __init__(self, appname, subjpreds=None, tag_id='', value=None, tagvals=None, queryopts={}):
        Node.__init__(self, appname)
        if subjpreds:
            self.subjpreds = subjpreds
        else:
            self.subjpreds = []
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
        self.globals['subjpreds'] = subjpreds
        self.globals['queryTarget'] = self.qtarget()

    def qtarget(self):
        if self.queryopts.get('view') == 'default':
            return None
        qpath = ''
        terms = []
        for pred in self.subjpreds:
            if pred.op:
                terms.append(urlquote(pred.tag) + pred.op + ",".join([ urlquote(val) for val in pred.vals ]))
            else:
                terms.append(urlquote(pred.tag))
        qpath = ';'.join(terms)
        return self.config['home'] + web.ctx.homepath + '/tags/' + qpath

    def get_tag_body(self):
        tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
        if tagdef == None:
            raise NotFound(data='tag definition "%s"' % self.tag_id)
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

        if self.contentType == 'text/html':
            unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True)
        else:
            unique = self.validate_subjpreds_unique(acceptName=True)
        if unique in [ True, None ]:
            versions = 'any'
        else:
            versions = 'latest'

        results = self.select_files_by_predlist(listtags=[ pred.tag for pred in self.subjpreds] 
                                                + [self.tag_id, 'owner', 'write users', 'name', 'version', 'tagdef', 'typedef'],
                                                versions=versions)
        if len(results) == 0:
            raise NotFound(data='subject matching "%s"' % predlist_linearize(self.subjpreds))
        self.subjects = [ res for res in results ]

        if len(self.subjects) == 1 \
           and self.subjects[0][self.tag_id] == None \
           and self.contentType not in ['text/uri-list', 'text/html']:
            if self.value == None:
                raise NotFound(data='tag "%s" on subject matching "%s"' % (self.tag_id, predlist_linearize(self.subjpreds)))
            elif self.value == '':
                raise NotFound(data='tag "%s" = "" on subject matching "%s"' % (self.tag_id, predlist_linearize(self.subjpreds)))
            else:
                raise NotFound(data='tag "%s" = "%s" on subject matching "%s"' % (self.tag_id, self.value, predlist_linearize(self.subjpreds)))

        for subject in self.subjects:
            self.txlog('GET', dataset=self.subject2identifiers(subject)[0], tag=self.tag_id)
            
        return None

    def get_tag_postCommit(self, values):
        web.header('Content-Type', self.contentType)

        subject = self.subjects[0]
        if self.tagdef.multivalue:
            values = subject[self.tag_id]
            if values == None:
                values = []
        else:
            values = [ subject[self.tag_id] ]
            
        if self.contentType == 'application/x-www-form-urlencoded':
            if len(values) > 0:
                return "&".join([(urlquote(self.tag_id) + '=' + urlquote(mystr(val))) for val in values])
            else:
                return urlquote(self.tag_id)
        elif self.contentType == 'text/uri-list':
            if self.typestr == 'url':
                return '\n'.join(values + [''])
            else:
                raise Conflict('Content-Type text/uri-list not appropriate for tag type "%s".' % self.typestr)
        elif self.contentType == 'text/plain':
            return '\n'.join(values) + '\n'
        else:
            # 'text/html'
            if self.queryopts.get('values', None) == 'basic':
                self.globals['smartTagValues'] = False
            
            if len(self.subjects) == 1:
                return self.renderlist('Tag "%s" for subject matching "%s"' % (self.tag_id, predlist_linearize(self.subjpreds)),
                                       [self.render.FileTagExisting('', self.subjects[0], [self.tagdef])])
            else:
                return self.renderlist('Tag "%s" for subjects matching "%s"' % (self.tag_id, predlist_linearize(self.subjpreds)),
                                       [self.render.FileTagValExisting('', self.subjects, [self.tagdef])])

    def GETtag(self, uri):
        # RESTful get of exactly one tag on one file...
        return self.dbtransact(self.get_tag_body, self.get_tag_postCommit)

    def get_all_body(self):
        self.txlog('GET ALL TAGS', dataset=self.subjpreds)

        
        try_default_view = True
        self.listtags = self.queryopts.get('list', [])
        if not self.listtags:
            view = self.select_view(self.queryopts.get('view', None), None)
            if view:
                self.listtags = view['tag list tags']
                try_default_view = False
        else:
            try_default_view = False

        if type(self.listtags) == type('text'):
            self.listtags = self.listtags.split(',')

        predtags = [ pred.tag for pred in self.subjpreds ]
        extratags = [ 'name', 'version', 'tagdef', 'typedef', 'write users', 'file', 'url' ]

        all = self.globals['tagdefsdict'].values()
        if len(self.listtags) > 0:
            all = [ tagdef for tagdef in all if tagdef.tagname in self.listtags or tagdef.tagname in predtags ]
        else:
            self.listtags = [ tagdef.tagname for tagdef in all ]
        all.sort(key=lambda tagdef: tagdef.tagname)

        unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True)
        if unique == False:
            versions = 'latest'
        else:
            # unique is True or None
            versions = 'any'

        files = [ file for file in self.select_files_by_predlist(listtags=self.listtags + predtags + extratags, versions=versions)  ]
        if len(files) == 0:
            raise NotFound('subject matching "%s"' % self.subjpreds)
        elif len(files) == 1:
            self.subject = files[0]
            self.datapred, self.dataid, self.dataname, self.subject.dtype = self.subject2identifiers(self.subject)

            if try_default_view and self.subject.dtype:
                view = self.select_view(self.subject.dtype)
                if view['tag list tags']:
                    self.listtags = view['tag list tags']
        else:
            if try_default_view:
                view = self.select_view('default')
                if view['tag list tags']:
                    self.listtags = view['tag list tags']

        all = [ tagdef for tagdef in all if tagdef.tagname in self.listtags or tagdef.tagname in predtags ]

        length = 0
        for file in files:
            for tagname in self.listtags:
                length = listOrStringMax(file[tagname], length)

        return (files, all, length)
    
    def get_title_one(self):
        return 'Tags for subject matching "%s"' % (self.dataname)

    def get_title_all(self):
        return 'Tags for subjects matching "%s"' % (predlist_linearize(self.subjpreds))

    def get_all_html_render(self, results):
        files, all, length = results
        #web.debug(system, userdefined, all)
        if self.queryopts.get('values', None) == 'basic':
            self.globals['smartTagValues'] = False
            
        if len(files) == 1:
            self.globals['version'] = None
            return self.renderlist(self.get_title_one(),
                                   [self.render.FileTagExisting('', files[0], all)])

        else:
            return self.renderlist(self.get_title_all(),
                                   [self.render.FileTagValExisting('', files, all)])
 
    def get_all_postCommit(self, results):
        files, all, length = results

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
                            if tagdef.typestr == 'empty':
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
        self.globals['referer'] = self.config['home'] + uri
        try:
            self.view_type = urllib.unquote_plus(self.storage.view)
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
        unique = self.validate_subjpreds_unique(acceptName=True)
        if unique:
            versions = 'any'
        else:
            versions = 'latest'
        
        list_additional =  ['owner', 'write users', 'Image Set']
        if self.tag_id:
            list_additional.append(self.tag_id)
        results = self.select_files_by_predlist(listtags=[ pred.tag for pred in self.subjpreds] + list_additional, versions=versions)
        if len(results) == 0:
            raise NotFound(data='subject matching "%s"' % self.subjpreds)
        self.subject = results[0]
        self.id = self.subject.id

        # custom DEI EIU hack, proxy tag ops on Image Set to all member files
        if self.subject['Image Set']:
            path = [ ( [ web.Storage(tag='id', op='=', vals=[self.id]) ], ['vcontains'], [] ),
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
            for value in self.tagvals[tag_id]:
                self.set_tag(self.subject, tagdef, value)
                if tag_id not in ['Image Set', 'contains', 'vcontains', 'list on homepage' ]:
                    for subfile in subfiles:
                        self.enforce_tag_authz('write', subfile, tagdef)
                        self.txlog('SET', dataset=self.subject2identifiers(subfile)[0], tag=tag_id, value=value)
                        self.set_tag(subfile, tagdef, value)

        if not self.referer:
            # set updated referer based on updated subject, unless client provided a referer
            self.referer = '/tags/' + self.subject2identifiers(self.subject)[0]
            
        return None

    def put_postCommit(self, results):
        return ''

    def PUT(self, uri):
        keys = self.tagvals.keys()
        if len(keys) == 1:
            self.tag_id = keys[0]
            
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

    def delete_body(self, previewOnly=False):
        unique = self.validate_subjpreds_unique(acceptName=True, acceptBlank=True)
        if unique == False:
            versions = 'latest'
        else:
            # unique is True or None
            versions = 'any'
         
        results = self.select_files_by_predlist(listtags=[ pred.tag for pred in self.subjpreds]
                                                + [self.tag_id, 'owner', 'write users', 'Image Set'],
                                                versions=versions)
        if len(results) == 0:
            raise NotFound(data='subject matching "%s"' % self.subjpreds)
        self.subjects = [ res for res in results ]

        tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
        if tagdef == None:
            raise NotFound('tagdef="%s"' % self.tag_id)

        if previewOnly:
            return None

        # find subfiles of all subjects which are tagged Image Set
        path = [ ( self.subjpreds + [ web.Storage(tag='Image Set', op='', vals=[]) ], ['vcontains'], [] ),
                 ( [], [], [] ) ]
        self.subfiles = self.select_files_by_predlist_path(path=path)

        for subject in self.subjects:
            self.enforce_tag_authz('write', subject, tagdef)
            self.txlog('DELETE', dataset=self.subject2identifiers(subject)[0], tag=self.tag_id, value=self.value)
            self.delete_tag(subject, tagdef, self.value)
            
        if self.tag_id in [ 'read users', 'write users' ]:
            for subfile in subfiles:
                self.enforce_tag_authz('write', subfile, tagdef)
                self.txlog('DELETE', dataset=self.subject2identifiers(subfile)[0], tag=self.tag_id, value=self.value)
                self.delete_tag(subfile, tagdef, self.value)

        if not self.referer:
            if len(self.subjects) == 1:
                # set updated referer based on single match
                self.referer = '/tags/' + self.subject2identifiers(self.subjects[0])[0]
            else:
                # for multi-subject results, redirect to subjpreds, which may no longer work but never happens in GUI
                self.referer = '/tags/' + predlist_linearize(self.subjpreds)
            
        return None

    def delete_postCommit(self, results):
        return ''

    def DELETE(self, uri):
        # RESTful delete of exactly one tag on 1 or more files...
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

class Query (Node):
    __slots__ = [ 'subjpreds', 'queryopts', 'action' ]
    def __init__(self, appname, queryopts={}, path=[]):
        Node.__init__(self, appname)
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
            subjpreds, listtags, ordertags = elem
            terms = []
            for pred in subjpreds:
                if pred.op:
                    terms.append(urlquote(pred.tag) + pred.op + ",".join([ urlquote(val) for val in pred.vals ]))
                else:
                    terms.append(urlquote(pred.tag))
            if not listtags or len(listtags) == 1 and listtags[0] in [ 'contains', 'vcontains' ]:
                listpart = ''
            else:
                listpart = '(' + ','.join([ urlquote(tag) for tag in listtags ]) + ')'
            qpath.append( ';'.join(terms) + listpart )
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

        self.globals['queryTarget'] = self.qtarget()
        self.globals['showVersions'] = self.showversions
            
        def body():
            listtags = self.queryopts.get('list', self.path[-1][1])
            writetags = None
            if type(listtags) == type('text'):
                listtags = listtags.split(',')
            if len(listtags) == 0:
                view = self.select_view(self.globals['view'])
                listtags = view['file list tags']
                writetags = view['file list tags write']

            self.limit = self.queryopts.get('limit', 25)
            if self.limit == 'none':
                self.limit = None
            elif type(self.limit) == type('text'):
                try:
                    self.limit = int(self.limit)
                except:
                    self.limit = 25

            listtags = [ t for t in listtags ]
            builtinlist = [ 'id' ] 
            listtags = builtinlist + [ tag for tag in listtags if tag not in builtinlist ]
            self.globals['filelisttags'] = listtags
            self.globals['filelisttagswrite'] = writetags

            subjpreds, listtags, ordertags = self.path[-1]
            self.path[-1] = subjpreds, list(self.globals['filelisttags']), ordertags
            # we always want these for subject psuedo-column
            self.path[-1][1].append('file')
            self.path[-1][1].append('name')
            self.path[-1][1].append('version')
            self.path[-1][1].append('tagdef')
            self.path[-1][1].append('typedef')
            self.path[-1][1].append('config')
            self.path[-1][1].append('view')
            self.path[-1][1].append('Image Set')
            self.path[-1][1].append('write users')
            self.path[-1][1].append('modified')

            for i in range(0, len(self.path[-1][1])):
                self.path[-1][1][i] = web.Storage(tag=self.path[-1][1][i], op=None, vals=[])

            return self.select_files_by_predlist_path(path=self.path, versions=versions, limit=self.limit)

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
                    tagvals.append( ( 'name', file.name ) )
                tagvals = dict(tagvals)
                for tagname in jsonMungeTags:
                    tagvals[tagname] = str(tagvals[tagname])
                return jsonWriter(tagvals)

            self.setNoCache()

            if self.action in set(['add', 'delete']):
                raise web.seeother(self.globals['queryTarget'] + '?action=edit&versions=%s' % versions )

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
                                       [self.render.QueryAdd(self.ops),
                                        self.render.QueryView(self.ops, self.subjpreds),
                                        self.render.FileList(files, showversions=self.showversions, limit=self.limit)])

        for res in self.dbtransact(body, postCommit):
            yield res


