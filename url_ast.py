
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
import re
import os
import webauthn
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote, urlunquote, idquote, jsonWriter, parseBoolString, predlist_linearize, path_linearize, downcast_value, jsonFileReader
from rest_fileio import FileIO, LogFileIO
import subjects
import json
import datetime

jsonMungeTypes = set([ datetime.datetime, datetime.date ])

def jsonMunger(file, listtags):
    
    def mungeVal(value):
        if type(value) == tuple:
            return [ mungeVal(v) for v in value ]
        elif type(value) in jsonMungeTypes:
            try:
                return str(value)
            except:
                return value
        else:
            return value

    def mungePair(tag, value):
        if type(value) == list:
            return ( tag, [ mungeVal(v) for v in value ] )
        else:
            return ( tag, mungeVal(value) )

    return dict([ mungePair( tag, file[tag] ) for tag in listtags ])

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
    elif type(val) not in [ str, unicode ]:
        return str(val)
    else:
        return val

def yield_json(files, tags):
    yield '['
    if len(files) > 0:
        yield jsonWriter(jsonMunger(files[0], tags)) + '\n'
    if len(files) > 1:
        for i in range(1,len(files)):
            yield ',' + jsonWriter(jsonMunger(files[i], tags)) + '\n'
    yield ']\n'

def yield_csv(files, tags):
    def wrapval(val):
        if val == None:
            return ''
        if type(val) in [ list, set ]:
            return ' '.join([wrapval(v) for v in val])
        if type(val) not in [ str, unicode ]:
            val = '%s' % val
        return '"' + val.replace('"','""') + '"'

    yield  ','.join([ wrapval(tag) for tag in tags ]) + '\n'
    for file in files:
        yield ','.join([ wrapval(file[tag]) for tag in tags ]) + '\n'
    return

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

    def __init__(self, parser, appname, queryopts=None):
        self.appname = appname
        Application.__init__(self, parser, queryopts)

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
            self.emit_headers()
            self.header('Location', results)
            self.header('Content-Type', 'text/plain')
            return results

        self.storage = web.input()
        
        try:
            self.table = urlunquote(self.storage.table)
        except:
            pass
        
        return self.dbtransact(body, postCommit)

class Study (Node):
    """Represents a study URI

       GET tagfiler/study?action=upload
    """

    __slots__ = []

    def __init__(self, parser, appname, subjpreds=[], queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
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
            self.action = urlunquote(self.storage.action)
        except:
            pass

        try:
            self.study_type = urlunquote(self.storage.type)
        except:
            pass

        try:
            self.direction = urlunquote(self.storage.direction)
        except:
            pass

        try:
            self.status = urlunquote(self.storage.status)
        except:
            pass

        def body():
            files = []

            config = self.select_config_cached(self.study_type)
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
                        raise NotFound(self, 'study "%s@%s"' % (self.name, self.version))
                else:
                    self.subject = results[0]
                    self.datapred, self.dataid, self.dataname, self.subject.dtype = self.subject2identifiers(self.subject)
                    files = self.subject.vcontains
                    if not files:
                        files = []
    
                self.globals['appletTagvals'] = sorted([ (tagname,
                                                   [ self.subject[tagname] ])
                                                  for tagname in self.globals['appletTagnames'] ], key=lambda tagdef: tagdef[0].lower())
                
            elif self.action == 'upload' or self.action == 'download':
                self.globals['tagdefsdict'] = dict([ item for item in self.globals['tagdefsdict'].iteritems()
                                                     if item[0] in self.globals['appletTagnames'] ])
            return files
    
        def postCommit(files):
            self.emit_headers()
            if self.action == 'upload':
                self.header('Content-Type', 'text/html')
                return self.renderlist("Study Upload",
                                       [self.render.TreeUpload()])
            elif self.action == 'download':
                self.globals['version'] = self.version
                self.header('Content-Type', 'text/html')
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
                    self.header('Content-Type', 'text/html')
                    return self.renderlist(None,
                                           [self.render.TreeStatus(self.name, self.direction, success, error, files)])
                else:
                    url = '/appleterror'
                    if self.status:
                        url += '?status=%s' % urlquote(self.status)
                    raise web.seeother(self, url)
            else:
                raise BadRequest(self, 'Unrecognized action form field.')

        return self.dbtransact(body, postCommit)

    def PUT(self, uri):
        self.storage = web.input()
        try:
            self.study_size = int(urlunquote(self.storage.study_size))
        except:
            pass

        try:
            self.count = int(urlunquote(self.storage.count))
        except:
            pass

        try:
            self.status = urlunquote(self.storage.status)
        except:
            pass

        try:
            self.direction = urlunquote(self.storage.direction)
        except:
            pass

        try:
            self.key = urlunquote(self.storage.key)
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
                raise Conflict(self, 'The size of the uploaded dataset "%s" does not match original file(s) size.' % (self.name))
            return ''

        return self.dbtransact(body, postCommit)

class AppletError (Node):
    """Represents an appleterror URI

       GET tagfiler/appleterror?status=string
    """

    __slots__ = []

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        self.action = None
        self.status = None

    def GET(self, uri):
        try:
            self.status = urlunquote(self.storage.status)
        except:
            pass

        # the applet needs to manage expiration itself
        # since it may be active while the html page is idle
        target = self.config['home'] + web.ctx.homepath
        self.setNoCache()
        self.emit_headers()
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
        Node.__init__(self, parser, appname, queryopts)
        self.globals['view'] = None

    def GET(self, uri):
        
        self.globals['referer'] = self.config['home'] + uri
        self.storage = web.input()

        def body():
            tagdefs = self.globals['tagdefsdict'].items()

            listtags = self.queryopts.get('list', None)
            writetags = None
            if not listtags:
                view = self.select_view(self.globals['view'])
                if view:
                    listtags = view['file list tags']
                    writetags = view['file list tags write']
                else:
                    listtags = []
                    writetags = []

            builtinlist = [ 'id' ]
            self.globals['filelisttags'] = builtinlist + [ tag for tag in listtags if tag not in builtinlist ]
            self.globals['filelisttagswrite'] = writetags
            
            if self.globals['tagdefsdict'].has_key('list on homepage'):
                subjpreds = [ web.Storage(tag='list on homepage', op=None, vals=[]) ]
                self.homepage = True
            else:
                subjpreds=[]
                self.homepage = False

            listpreds = [ web.Storage(tag=t, op=None, vals=[]) for t in set(self.globals['filelisttags']).union(set(['Image Set', 'id', 'Study Type',
                                                                                                                     'name', 'version',
                                                                                                                     'tagdef', 'typedef',
                                                                                                                     'config', 'view', 'url'])) ]

            if self.globals['tagdefsdict'].has_key('homepage order') and self.homepage:
                ordertags = [('homepage order', ':asc:')]
            else:
                ordertags = []

            querypath = [ ( subjpreds, listpreds, ordertags ) ]
            self.set_http_etag(self.select_predlist_path_txid(querypath))
            if self.http_is_cached():
                return None
            else:
                return self.select_files_by_predlist_path(querypath)
        
        def postCommit(files):
            target = self.config['home'] + web.ctx.homepath
            if files == None:
                web.ctx.status = '304 Not Modified'
            self.emit_headers()
            if files == None:
                return ''
            elif self.homepage:
                self.header('Content-Type', 'text/html')
                return self.renderlist(None,
                                       [self.render.Homepage(files)])
            else:
                self.header('Content-Type', 'text/html')
                return self.renderlist(None,
                                       [self.render.Commands(),
                                        self.render.FileList(files)])
                
        action = None
        name = None
        filetype = None
        readers = None
        writers = None
        try:
            action = urlunquote(self.storage.action)
            try:
                name = urlunquote(self.storage.name)
                filetype = urlunquote(self.storage.type)
                readers = urlunquote(self.storage['read users'])
                writers = urlunquote(self.storage['write users'])
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
                def body():
                    return None
                def postCommit(ignore):
                    self.header('Content-Type', 'text/html')
                    return self.renderlist("Define a dataset",
                                           [self.render.NameForm()])
                return self.dbtransact(body, postCommit)
        else:
            try:
                self.globals['view'] = urlunquote(self.storage.view)
            except:
                pass
            return self.dbtransact(body, postCommit)

    def POST(self, uri):
        ast = FileId(parser=self.url_parse_func,
                     appname=self.appname,
                     path=[],
                     queryopts=self.queryopts)
        ast.preDispatchFake(uri, self)
        return ast.POST(uri)

class LogList (Node):
    """Represents a bare LOG/ URI

       GET LOG or LOG/  -- gives a listing
       """

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)

    def GET(self, uri):
        if not self.authn.hasRoles(['admin']):
            raise Forbidden(self, 'listing of log files')
        
        if self.config['log path']:
            lognames = sorted(os.listdir(self.config['log path']), reverse=True)
                              
        else:
            lognames = []
        
        target = self.config['home'] + web.ctx.homepath
        
        self.http_vary.add('Accept')
        self.emit_headers()

        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                # return raw results for REST client
                self.header('Content-Type', 'text/uri-list')
                return self.render.LogUriList(lognames)
            elif acceptType == 'text/html':
                break

        self.header('Content-Type', 'text/html')
        return self.renderlist("Archived logs",
                               [self.render.LogList(lognames)])

class Contact (Node):
    """Represents a bare CONTACT URI

       GET CONTACT
       """

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        self.globals['webauthnrequire'] = False

    def GET(self, uri):
        
        self.setNoCache()
        self.emit_headers()
        self.header('Content-Type', 'text/html')
        return self.renderlist("Contact Us",
                               [self.render.Contact()])

class FileId(Node, FileIO):
    """Represents a direct FILE/subjpreds URI

       Just creates filename and lets FileIO do the work.

    """
    __slots__ = [ 'storagename', 'dtype', 'queryopts' ]
    def __init__(self, parser, appname, path, queryopts={}, versions='any', storage=None):
        Node.__init__(self, parser, appname, queryopts)
        FileIO.__init__(self, parser=parser)
        self.path = [ ( e[0], e[1], [] ) for e in path ]
        self.versions = versions
        if storage:
            self.storage = storage

class Subject(Node, subjects.Subject):
    __slots__ = [ 'storagename', 'dtype', 'queryopts' ]
    def __init__(self, parser, appname, path, queryopts={}, storage=None):
        Node.__init__(self, parser, appname, queryopts)
        subjects.Subject.__init__(self)
        self.path = [ ( e[0], e[1], [] ) for e in path ]
        if storage:
            self.storage = storage

class LogId(Node, LogFileIO):
    """Represents a direct LOG/subjpreds URI

       Just creates filename and lets LogFileIO do the work.

    """
    __slots__ = [ ]
    def __init__(self, parser, appname, name, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        LogFileIO.__init__(self)
        self.name = name

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

    __slots__ = [ 'tag_id', 'typestr', 'target', 'action', 'tagdefs', 'writepolicy', 'readpolicy', 'multivalue', 'queryopts' ]

    def __init__(self, parser, appname, tag_id=None, typestr=None, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        self.tag_id = tag_id
        self.typestr = typestr
        self.writepolicy = None
        self.readpolicy = None
        self.multivalue = None
        self.is_unique = None
        self.action = None
        self.tagdefs = {}

    def GET(self, uri):

        if self.tag_id != None:
            if len(self.queryopts) > 0:
                raise BadRequest(self, data="Query options are not supported on this interface.")
            else:
                return self.GETone(uri)
        else:
            return self.GETall(uri)

    def GETall(self, uri):

        def body():
            predefined = [ tagdef for tagdef in self.select_tagdef(subjpreds=[web.Storage(tag='owner', op=':absent:', vals=[])], order='tagdef') ]
            userdefined = [ tagdef for tagdef in self.select_tagdef(subjpreds=[web.Storage(tag='owner', op=None, vals=[])], order='tagdef') ]
            types = self.get_type()
            
            return (predefined, userdefined, types)

        def postCommit(defs):
            self.emit_headers()
            self.header('Content-Type', 'text/html')
            predefined, userdefined, types = defs
            test_tagdef_authz = lambda mode, tag: self.test_tagdef_authz(mode, tag)
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting('User', userdefined),
                                    self.render.TagdefExisting('System', predefined )])

        if len(self.queryopts) > 0:
            raise BadRequest(self, data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)

    def GETone(self,uri):

        def body():
            results = self.select_tagdef(self.tag_id)
            if len(results) == 0:
                raise NotFound(self, data='tag definition %s' % (self.tag_id))
            return results[0]

        def postCommit(tagdef):
            try:
                self.emit_headers()
                self.header('Content-Type', 'application/x-www-form-urlencoded')
                return ('typestr=' + urlquote(tagdef.typestr) 
                        + '&readpolicy=' + urlquote(tagdef.readpolicy)
                        + '&writepolicy=' + urlquote(tagdef.writepolicy)
                        + '&multivalue=' + urlquote(tagdef.multivalue)
                        + '&owner=' + urlquote(tagdef.owner))
            except:
                raise NotFound(self, data='tag definition %s' % (self.tag_id))

        if len(self.queryopts) > 0:
            raise BadRequest(self, data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)

    def DELETE(self, uri):
        
        def body():
            tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
            if tagdef == None:
                raise NotFound(self, data='tag definition %s' % (self.tag_id))
            self.enforce_tagdef_authz('write', tagdef)
            self.delete_tagdef(tagdef)
            return ''

        def postCommit(results):
            self.emit_headers()
            return ''

        if len(self.queryopts) > 0:
            raise BadRequest(self, data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)
                
    def PUT(self, uri):

        if self.tag_id == None:
            raise BadRequest(self, data="Tag definitions require a non-empty tag name.")

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
                self.multivalue = downcast_value('boolean', self.queryopts['multivalue'])
            except:
                self.multivalue = False

        if self.is_unique == None:
            try:
                self.is_unique = downcast_value('boolean', self.queryopts['unique'])
            except:
                self.is_unique = False

        def body():
            if len( set(self.config['tagdef write users']).intersection(set(self.authn.roles).union(set('*'))) ) == 0:
                raise Forbidden(self, 'creation of tag definitions')
                
            results = self.select_tagdef(self.tag_id, enforce_read_authz=False)
            if len(results) > 0:
                raise Conflict(self, data="Tag %s is already defined." % self.tag_id)
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
                        try:
                            typestr = storage['type-%s' % (key[4:])]
                        except:
                            raise BadRequest(self, data="A tag type must be specified.")
                        try:
                            readpolicy = storage['readpolicy-%s' % (key[4:])]
                        except:
                            raise BadRequest(self, data="A read policy must be specified.")
                        try:
                            writepolicy = storage['writepolicy-%s' % (key[4:])]
                        except:
                            raise BadRequest(self, data="A write policy must be specified.")
                        try:
                            multivalue = storage['multivalue-%s' % (key[4:])]
                        except:
                            raise BadRequest(self, data="The value cardinality must be specified.")
                        try:
                            unique = storage['unique-%s' % (key[4:])]
                        except:
                            unique = 'false'
                        self.tagdefs[storage[key]] = (typestr, readpolicy, writepolicy, downcast_value('boolean', multivalue), downcast_value('boolean', unique))
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
            raise BadRequest(self, data="Error extracting form data.")

        def body():
            if self.action == 'add':
                if len( set(self.config['tagdef write users']).intersection(set(self.authn.roles).union(set('*'))) ) == 0:
                    raise Forbidden(self, 'creation of tag definitions')
                
                for tagname in self.tagdefs.keys():
                    self.tag_id = tagname
                    self.typestr, self.readpolicy, self.writepolicy, self.multivalue, self.is_unique = self.tagdefs[tagname]
                    results = self.select_tagdef(self.tag_id, enforce_read_authz=False)
                    if len(results) > 0:
                        raise Conflict(self, data="Tag %s is already defined." % self.tag_id)
                    self.insert_tagdef()
            elif self.action == 'delete' or self.action == 'CancelDelete':
                tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
                if tagdef == None:
                    raise NotFound(self, 'tag definition "%s"' % self.tag_id)
                self.globals['dataname'] = self.tag_id
                self.globals['datapred'] = urlquote(self.tag_id)
                self.enforce_tagdef_authz('write', tagdef)
                return None
            elif self.action == 'ConfirmDelete':
                tagdef = self.globals['tagdefsdict'].get(self.tag_id, None)
                if tagdef == None:
                    raise NotFound(self, 'tag definition "%s"' % self.tag_id)
                self.enforce_tagdef_authz('write', tagdef)
                self.delete_tagdef(tagdef)
            else:
                raise BadRequest(self, data="Form field action=%s not understood." % self.action)
            return None

        def postCommit(results):
            if self.action == 'delete':
                self.globals['name'] = self.tag_id
                self.globals['version'] = None
                self.emit_headers()
                self.header('Content-Type', 'text/html')
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
        Node.__init__(self, parser, appname, queryopts)
        if path:
            self.path = path
        else:
            self.path = [ ([], [], []) ]
        self.referer = None
        self.globals['queryTarget'] = self.qtarget()
        self.globals['queryAllTags'] = None

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
        self.path_modified, self.listtags, writetags, self.limit, self.offset, self.versions = \
              self.prepare_path_query(self.path,
                                      list_priority=['path', 'list', 'view', 'subject', 'all'],
                                      list_prefix='tag',
                                      extra_tags=
                                      [ 'id', 'file', 'name', 'version', 'Image Set', 'Study Type',
                                        'write users', 'modified' ] 
                                      + [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique ])

        self.http_vary.add('Accept')
        self.set_http_etag(self.select_predlist_path_txid(self.path_modified, versions=self.versions))
        if self.http_is_cached():
            return None, None, None
        
        self.txlog('GET TAGS', dataset=path_linearize(self.path_modified))

        if len(self.listtags) == len(self.globals['tagdefsdict'].values()) and self.queryopts.get('view') != 'default':
            try_default_view = True
        else:
            try_default_view = False
            self.globals['queryAllTags'] = self.qAllTags()
            
        all = [ tagdef for tagdef in self.globals['tagdefsdict'].values() if tagdef.tagname in self.listtags ]
        all.sort(key=lambda tagdef: tagdef.tagname)

        files = [ file for file in self.select_files_by_predlist_path(self.path_modified, versions=self.versions, limit=self.limit)  ]
        if len(files) == 0:
            raise NotFound(self, 'subject matching "%s"' % predlist_linearize(self.path_modified[-1][0], lambda x: x))
        else:
            subject = files[0]
            datapred, dataid, dataname, subject.dtype = self.subject2identifiers(subject)

            if try_default_view and subject.dtype:
                view = self.select_view(subject.dtype)
                if view and view['tag list tags']:
                    self.listtags = view['tag list tags']
                    self.globals['queryAllTags'] = self.qAllTags()

        length = 0
        for file in files:
            for tagname in self.listtags:
                length = listOrStringMax(file[tagname], length)

        return (files, all, length)

    def get_postCommit(self, results):
        files, all, length = results

        if files == None:
            web.ctx.status = '304 Not Modified'
            return ''

        self.emit_headers()
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                self.header('Content-Type', 'text/uri-list')
                self.globals['str'] = str 
                return self.render.FileTagUriList(files, all)
            elif acceptType == 'application/x-www-form-urlencoded' and len(files) == 1:
                self.header('Content-Type', 'application/x-www-form-urlencoded')
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
            elif acceptType == 'text/csv':
                self.header('Content-Type', 'text/csv')
                return ''.join([ res for res in yield_csv(files, [td.tagname for td in all]) ])
            elif acceptType == 'application/json':
                self.header('Content-Type', 'application/json')
                return ''.join([ res for res in yield_json(files, [td.tagname for td in all]) ])
            elif acceptType == 'text/plain' and len(files) == 1 and len(self.listtags) == 1:
                self.header('Content-Type', 'text/plain')
                val = files[0][self.listtags[0]]
                if type(val) == list:
                    return '\n'.join(val) + '\n'
                else:
                    return '%s\n' % val
            elif acceptType == 'text/html':
                break
                
        # render HTML result
        self.header('Content-Type', 'text/html')
        if self.queryopts.get('values', None) == 'basic':
            self.globals['smartTagValues'] = False

        simplepath = [ x for x in self.path ]
        simplepath[-1] = simplepath[-1][0], [], []

        tagdefs = [ x for x in all if x.tagname in self.listtags ]

        title = u'Tag(s) for subject matching "' + path_linearize(simplepath, lambda x: x) + u'"'
        if len(files) == 1:
            return self.renderlist(title,
                                   [self.render.FileTagExisting('', files[0], tagdefs)])
        else:
            return self.renderlist(title,
                                   [self.render.FileTagValExisting('', files, tagdefs)])

    def GET(self, uri=None):
        # dispatch variants, browsing and REST
        self.globals['referer'] = self.config['home'] + uri
        try:
            self.view_type = urlunquote(self.storage.view)
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
                raise BadRequest(self, 'Invalid operation "%s" for tag binding in PUT.' % pred.op)
            if self.tagvals.has_key(pred.tag):
                raise BadRequest(self, 'Tag "%s" occurs in more than one binding predicate in PUT.' % pred.tag)
            self.tagvals[pred.tag] = pred.vals
        
        listpreds =  [ web.Storage(tag=tag,op=None,vals=[])
                       for tag in ['id', 'owner', 'write users', 'Image Set', 'Study Type', 'url', 'incomplete'] + [p.tag for p in subjpreds]  ]

        simplepath = [ x for x in self.path ]
        simplepath[-1] = ( simplepath[-1][0], [], [] )

        self.path_modified = [ x for x in self.path ]
        self.path_modified[-1] = (subjpreds, listpreds, ordertags)

        ignorenotfound = parseBoolString(self.storage.get('ignorenotfound', 'false'))

        results = self.select_files_by_predlist_path(self.path_modified, versions=versions)
        if len(results) == 0 and not ignorenotfound:
            raise NotFound(self, data='subject matching "%s"' % path_linearize(simplepath, lambda x: x))

        for subject in results:
            if not self.referer:
                # set updated referer based on updated subject(s), unless client provided a referer
                if len(results) != 1:
                    self.referer = '/tags/' + path_linearize(self.path)
                else:
                    self.referer = '/tags/' + self.subject2identifiers(subject)[0]
            
            # custom DEI EIU hack, proxy tag ops on Image Set to all member files
            if subject['Image Set']:
                path = [ ( [ web.Storage(tag='id', op='=', vals=[subject.id]) ], [web.Storage(tag='vcontains',op=None,vals=[])], [] ),
                         ( [], [], [] ) ]
                subfiles = self.select_files_by_predlist_path(path=path)
            else:
                subfiles = []

            for tag_id in self.tagvals.keys():
                tagdef = self.globals['tagdefsdict'].get(tag_id, None)
                if tagdef == None:
                    raise NotFound(self, data='tag definition "%s"' % tag_id)
                self.enforce_tag_authz('write', subject, tagdef)
                self.txlog('SET', dataset=self.subject2identifiers(subject)[0], tag=tag_id, value=','.join(['%s' % val for val in self.tagvals[tag_id]]))
                if self.tagvals[tag_id]:
                    for value in self.tagvals[tag_id]:
                        self.set_tag(subject, tagdef, value)
                        if tag_id not in ['Image Set', 'contains', 'vcontains', 'list on homepage', 'key', 'check point offset' ] and not tagdef.unique:
                            for subfile in subfiles:
                                self.enforce_tag_authz('write', subfile, tagdef)
                                self.txlog('SET', dataset=self.subject2identifiers(subfile)[0], tag=tag_id, value=value)
                                self.set_tag(subfile, tagdef, value)
                else:
                    self.set_tag(subject, tagdef)
                    if tag_id not in ['Image Set', 'contains', 'vcontains', 'list on homepage', 'key', 'check point offset' ] and not tagdef.unique:
                        for subfile in subfiles:
                            self.enforce_tag_authz('write', subfile, tagdef)
                            self.txlog('SET', dataset=self.subject2identifiers(subfile)[0], tag=tag_id)
                            self.set_tag(subfile, tagdef)

            
        return None

    def put_postCommit(self, results):
        self.emit_headers()
        return ''

    def PUT(self, uri):
        try:
            content_type = web.ctx.env['CONTENT_TYPE'].lower()
        except:
            content_type = 'text/plain'
        
        if content_type in [ 'application/json' ]:
            if content_type == 'application/json':
                try:
                    input = jsonFileReader(web.ctx.env['wsgi.input'])
                except:
                    et, ev, tb = sys.exc_info()
                    web.debug('got exception "%s" parsing JSON input from client' % str(ev),
                              traceback.format_exception(et, ev, tb))
                    raise BadRequest(self, 'Invalid JSON input to bulk PUT of tags.')
                if type(input) != list:
                    raise BadRequest(self, 'JSON input must be a flat list of objects for bulk PUT of tags.')
                
            self.bulk_update_transact(input, on_missing='abort', on_existing='merge')
                
            web.ctx.status = '204 No Content'
            return ''

        elif content_type == 'application/x-www-form-urlencoded':
            # handle same entity body format we output in GETtag()
            #  tag=val&tag=val...
            content = web.ctx.env['wsgi.input'].read()
            tagvals = dict()
            for tagval in content.strip().split('&'):
                try:
                    tag, val = tagval.split('=')
                    tag = urlunquote(tag)
                    val = urlunquote(val)
                except:
                    raise BadRequest(self, 'Invalid x-www-form-urlencoded content.')

                if tag == '':
                    raise BadRequest(self, data="A non-empty tag name is required.")

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

        listpreds =  [ web.Storage(tag=tag,op=None,vals=[]) for tag in ['id', 'Image Set', 'Study Type', 'view', 'name', 'version', 'incomplete'] ] + origlistpreds

        simplepath = [ x for x in self.path ]
        simplepath[-1] = ( simplepath[-1][0], [], [] )

        self.path_modified = [ x for x in self.path ]
        self.path_modified[-1] = (subjpreds, listpreds, ordertags)
         
        results = self.select_files_by_predlist_path(self.path_modified, versions=versions)
        if len(results) == 0:
            raise NotFound(self, data='subject matching "%s"' % path_linearize(simplepath, lambda x: x))
        self.subjects = [ res for res in results ]

        # find subfiles of all subjects which are tagged Image Set
        path = [ ( subjpreds + [ web.Storage(tag='Image Set', op='', vals=[]) ], [web.Storage(tag='vcontains',op=None,vals=[])], [] ),
                 ( [], [web.Storage(tag='id',op=None,vals=[])], [] ) ]
        self.subfiles = dict([ (res.id, res) for res in self.select_files_by_predlist_path(path=path) ])

        for tag in set([pred.tag for pred in origlistpreds ]):
            tagdef = self.globals['tagdefsdict'].get(tag, None)
            if tagdef == None:
                raise NotFound(self, 'tagdef="%s"' % tag)

            if not previewOnly:
                for subject in self.subjects:
                    self.enforce_tag_authz('write', subject, tagdef)
                    if tagdef.typestr == 'empty' and subject[tag]:
                        vals = [None]
                    elif tagdef.multivalue:
                        if subject[tag]:
                            vals = subject[tag]
                        else:
                            vals = None
                    elif subject[tag] == None:
                        vals = None
                    else:
                        vals = [subject[tag]]

                    if vals:
                        self.txlog('DELETE', dataset=self.subject2identifiers(subject)[0], tag=tag, value=((vals[0]!=None) and ','.join([u'%s' % val for val in vals])) or None)
                        for val in vals:
                            self.delete_tag(subject, tagdef, val)
            
                        if tag in [ 'read users', 'write users' ]:
                            for subfile in self.subfiles.values():
                                self.enforce_tag_authz('write', subfile, tagdef)
                                self.txlog('DELETE', dataset=self.subject2identifiers(subfile)[0], tag=tag, value=((vals[0]!=None) and ','.join([u'%s' % val for val in vals])) or None)
                                for val in vals:
                                    self.delete_tag(subfile, tagdef, val)
                    else:
                        self.txlog('DELETE NONE MATCH', dataset=self.subject2identifiers(subject)[0], tag=tag)

        if not previewOnly and not self.referer:
            if len(self.subjects) == 1:
                # set updated referer based on single match
                self.referer = '/tags/' + self.subject2identifiers(self.subjects[0])[0]
            else:
                # for multi-subject results, redirect to subjpreds, which may no longer work but never happens in GUI
                self.referer = '/tags/' + path_linearize(simplepath)
            
        return None

    def delete_postCommit(self, results):
        self.emit_headers()
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
                op = '='
                if len(vals) == 0:
                    op = None
                listpreds.append( web.Storage(tag=tag, op=op, vals=vals) )
            try:
                self.referer = storage.referer
            except:
                self.referer = None
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception during filetags form post parsing',
                      traceback.format_exception(et, ev, tb))
            raise BadRequest(self, data="Error extracting form data.")

        self.path[-1] = (subjpreds, listpreds, ordertags)

        if action == 'put':
            return self.dbtransact(self.put_body, self.post_postCommit)
        elif action == 'delete':
            return self.dbtransact(self.delete_body, self.post_postCommit)
        else:
            raise BadRequest(self, data="Form field action=%s not understood." % action)

class Query (Node):
    __slots__ = [ 'subjpreds', 'queryopts', 'action' ]
    def __init__(self, parser, appname, queryopts={}, path=[]):
        Node.__init__(self, parser, appname, queryopts)
        self.path = path
        if len(self.path) == 0:
            self.path = [ ( [], [], [] ) ]
        self.subjpreds = self.path[-1][0]
        self.action = 'query'
        self.globals['view'] = None
        #self.log('TRACE', 'Query() constructor exiting')

    def qtarget(self):
        qpath = []
        for elem in self.path:
            subjpreds, listpreds, ordertags = elem
            #web.debug(listpreds)
            if listpreds:
                if len(listpreds) == 1 and listpreds[0].tag in [ 'contains', 'vcontains' ] and listpreds[0].op == None:
                    listpart = ''
                else:
                    listpart = '(%s)' % predlist_linearize(listpreds, sort=False)
            else:
                listpart = ''

            qpath.append( predlist_linearize(subjpreds, sort=False) + listpart )
        return self.config['home'] + web.ctx.homepath + '/query/' + '/'.join(qpath)

    def GET(self, uri):
        #self.log('TRACE', value='Query::GET() entered')
        # this interface has both REST and form-based functions
        
        # test if user predicate equals a predicate from subjpreds
        def equals(pred, userpred):
            return ({'tag' : pred.tag, 'op' : pred.op, 'vals' : str(pred.vals)} == userpred)

        try:
            self.title = self.queryopts['title']
        except:
            self.title = None

        try:
            self.globals['view'] = self.queryopts['view']
        except:
            pass

        contentType = 'text/html'

        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType in [ 'text/uri-list', 'text/html', 'application/json', 'text/csv' ]:
                contentType = acceptType
                break

        def body():
            #self.txlog('TRACE', value='Query::body entered')
            self.http_vary.add('Accept')

            path, self.listtags, writetags, self.limit, self.offset, self.versions = \
                  self.prepare_path_query(self.path,
                                          list_priority=['path', 'list', 'view', 'default'],
                                          list_prefix='file',
                                          extra_tags=[ ])

            #self.txlog('TRACE', value='Query::body query prepared')
            self.set_http_etag(txid=self.select_predlist_path_txid(self.path, versions=self.versions, limit=self.limit))
            #self.txlog('TRACE', value='Query::body txid computed')
            cached = self.http_is_cached()

            if cached:
                web.ctx.status = '304 Not Modified'
                return None
            elif contentType != 'text/html':
                self.txlog('QUERY', dataset=path_linearize(self.path))

                self.queryopts['range'] = self.query_range
                files = [file for file in  self.select_files_by_predlist_path(path=path, versions=self.versions, limit=self.limit, offset=self.offset) ]
                self.queryopts['range'] = None
                #self.txlog('TRACE', value='Query::body query returned')

                self.globals['filelisttags'] = [ 'id' ] + [x for x in self.listtags if x !='id']
                self.globals['filelisttagswrite'] = writetags

                return files
            else:
                self.globals['basepath'] = path_linearize(path[0:-1])
                self.globals['querypath'] = [ dict(spreds=[dict(s) for s in spreds],
                                                   lpreds=[dict(l) for l in lpreds],
                                                   otags=otags)
                                              for spreds, lpreds, otags in path ]
                self.globals['ops'] = Application.ops
                self.globals['opsExcludeTypes'] = Application.opsExcludeTypes
                return []

        def postCommit(files):
            self.emit_headers()
            if files == None:
                # caching short cut
                return
            
            if self.versions == 'any':
                self.showversions = True
            else:
                self.showversions = False
            
            self.globals['showVersions'] = self.showversions
            self.globals['queryTarget'] = self.qtarget()
                
            if self.action in set(['add', 'delete']):
                raise web.seeother(self.globals['queryTarget'] + '?action=edit&versions=%s' % self.versions )

            #self.log('TRACE', value='Query::body postCommit dispatching on content type')

            if contentType == 'text/uri-list':
                # return raw results for REST client
                if self.query_range:
                    raise BadRequest(self, 'Query option "range" not meaningful for text/uri-list result format.')
                self.header('Content-Type', 'text/uri-list')
                yield self.render.FileUriList(files)
                return
            elif contentType == 'text/csv':
                self.header('Content-Type', 'text/csv')
                for res in yield_csv(files, self.listtags):
                    yield res
                return
            elif contentType == 'application/json':
                self.header('Content-Type', 'application/json')
                for res in yield_json(files, self.listtags):
                    yield res
                return
            else:
                if self.query_range:
                    raise BadRequest(self, 'Query option "range" not supported for text/html result format.')
                self.header('Content-Type', 'text/html')
                for r in self.renderlist(self.title, [self.render.Query()]):
                    yield r
                return

        for res in self.dbtransact(body, postCommit):
            yield res

        #self.log('TRACE', value='Query::GET exiting')

class UI (Node):
    """Represents a generic template for the user interface"""

    def __init__(self, parser, appname, uiopts, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        #self.globals['uiopts'] = jsonWriter(uiopts)
        self.globals['uiopts'] = uiopts

    def GET(self, uri):
        self.header('Content-Type', 'text/html')
        return self.renderlist(None,
                               [self.render.UI()])


