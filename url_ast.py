
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
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote, urlunquote, idquote, jsonWriter, parseBoolString, predlist_linearize, path_linearize, downcast_value, jsonFileReader, jsonArrayFileReader, JSONArrayError
from rest_fileio import FileIO, LogFileIO
import subjects
from subjects import Node
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

class Subquery (object):
    """Stub AST node holds a query path that is not wrapped in a full URI.

       This class cannot be invoked by the URL dispatcher as it has no web methods."""
    def __init__(self, path):
        self.path = path
        self.is_subquery = True

    def __repr__(self):
        return "@(%s)" % path_linearize(self.path)

class TransmitNumber (Node):
    """Represents a transmitnumber URI

       POST tagfiler/transmitnumber
    """

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

            config = self.select_config_cached(self.db, self.study_type)
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
                self.header('Content-Type', 'application/json')
                params = {}
                params['tagfiler.server.url'] = self.globals['home']
                params['tagfiler.applet.test'] = self.globals['appletTestProperties']
                params['tagfiler.applet.log'] = self.globals['appletLogfile']
                params['custom.properties'] = self.globals['appletCustomProperties']
                params['tagfiler.connections'] = self.globals['clientConnections']
                params['tagfiler.allow.chunks'] = self.globals['clientUploadChunks']
                params['tagfiler.socket.buffer.size'] = self.globals['clientSocketBufferSize']
                params['tagfiler.chunkbytes'] = self.globals['clientChunkbytes']
                params['tagfiler.client.socket.timeout'] = self.globals['clientSocketTimeout']
                params['tagfiler.retries'] = self.globals['clientRetryCount']
                params['tagfiler.cookie.name'] = 'tagfiler'
                self.uiopts = {}
                self.uiopts['params'] = params
                self.uiopts['appletTagnames'] = self.globals['appletTagnames']
                self.uiopts['appletTagnamesRequire'] = self.globals['appletTagnamesRequire']
                return jsonWriter(self.uiopts)
            elif self.action == 'download':
                self.globals['version'] = self.version
                self.header('Content-Type', 'application/json')
                params = {}
                params['tagfiler.server.url'] = self.globals['home']
                params['tagfiler.server.transmissionnum'] = self.name
                params['tagfiler.server.version'] = self.globals['version']
                params['tagfiler.applet.test'] = self.globals['appletTestProperties']
                params['tagfiler.applet.log'] = self.globals['appletLogfile']
                params['custom.properties'] = self.globals['appletCustomProperties']
                params['tagfiler.connections'] = self.globals['clientConnections']
                params['tagfiler.allow.chunks'] = self.globals['clientUploadChunks']
                params['tagfiler.socket.buffer.size'] = self.globals['clientSocketBufferSize']
                params['tagfiler.chunkbytes'] = self.globals['clientChunkbytes']
                params['tagfiler.client.socket.timeout'] = self.globals['clientSocketTimeout']
                params['tagfiler.retries'] = self.globals['clientRetryCount']
                params['tagfiler.cookie.name'] = 'tagfiler'
                self.uiopts = {}
                self.uiopts['params'] = params
                return jsonWriter(self.uiopts)
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
                    self.header('Content-Type', 'application/json')
                    params = {}
                    params['name'] = self.name
                    params['direction'] = self.direction
                    params['success'] = success
                    params['error'] = error
                    params['files'] = files
                    params['appletTagvals'] = self.globals['appletTagvals']
                    params['version'] = self.globals['version']
                    self.uiopts = {}
                    self.uiopts['params'] = params
                    return jsonWriter(self.uiopts)
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
        return 'AppletError: %s' % self.status

class FileList (Node):
    """Represents a bare FILE/ URI

       GET  FILE  or FILE/         -- gives a listing
       GET  FILE?action=define     -- gives a new NameForm
       POST FILE?name=foo&type=t   -- redirects to GET FILE/name?type=t&action=define
    """

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
                return self.renderui(['home'])
            else:
                self.header('Content-Type', 'text/html')
                return self.renderui(['home'])
                
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
                    return 'Define a dataset'
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
        #if not self.authn.hasRoles(['admin']):
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

class FileId(FileIO):
    """Represents a direct FILE/subjpreds URI

       Just creates filename and lets FileIO do the work.

    """
    def __init__(self, parser, appname, path, queryopts={}, versions='any', storage=None):
        FileIO.__init__(self, parser, appname, path, queryopts)
        self.path = [ ( e[0], e[1], [] ) for e in path ]
        self.versions = versions
        if storage:
            self.storage = storage

class Subject(subjects.Subject):
    def __init__(self, parser, appname, path, queryopts={}, storage=None):
        subjects.Subject.__init__(self, parser, appname, path, queryopts)
        self.path = [ ( e[0], e[1], [] ) for e in path ]
        if storage:
            self.storage = storage

class LogId(LogFileIO):
    """Represents a direct LOG/subjpreds URI

       Just creates filename and lets LogFileIO do the work.

    """
    def __init__(self, parser, appname, name, queryopts={}):
        LogFileIO.__init__(self, parser, appname, [], queryopts)
        self.name = name

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

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
            return 'Tag definitions'

        if len(self.queryopts) > 0:
            raise BadRequest(self, data="Query options are not supported on this interface.")

        return self.renderui(['tagdef'], self.queryopts)

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
            if len( set(self.config['tagdef write users']).intersection(set(self.context.attributes).union(set('*'))) ) == 0:
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
                        try:
                            self.tagdefs[storage[key]] = (typestr, readpolicy, writepolicy, downcast_value('boolean', multivalue), downcast_value('boolean', unique))
                        except ValueError, e:
                            raise BadRequest(self, data=str(e))
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
                if len( set(self.config['tagdef write users']).intersection(set(self.context.attributes).union(set('*'))) ) == 0:
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
                return 'Delete Confirmation'
            else:
                # send client back to get form page again
                raise web.seeother('/tagdef')

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/subjpreds and TAGS/subjpreds/tagvals URIs"""

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
            url += '&' + opts
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
            return None, None
        
        self.txlog('GET TAGS', dataset=path_linearize(self.path_modified))

        if len(self.listtags) == len(self.globals['tagdefsdict'].values()) and self.queryopts.get('view') != 'default':
            try_default_view = True
        else:
            try_default_view = False
            self.globals['queryAllTags'] = self.qAllTags()
            
        all = [ tagdef for tagdef in self.globals['tagdefsdict'].values() if tagdef.tagname in self.listtags ]
        all.sort(key=lambda tagdef: tagdef.tagname)

        if self.acceptType == 'application/json':
            files = self.select_files_by_predlist_path(self.path_modified, versions=self.versions, limit=self.limit, json=True)
        else:
            files = list(self.select_files_by_predlist_path(self.path_modified, versions=self.versions, limit=self.limit))

        if len(files) == 0:
            raise NotFound(self, 'subject matching "%s"' % predlist_linearize(self.path_modified[-1][0], lambda x: x))

        return (files, all)

    def get_postCommit(self, results):
        files, all = results

        if files == None:
            web.ctx.status = '304 Not Modified'
            return
        
        self.emit_headers()
        if self.acceptType == 'text/html':
            self.header('Content-Type', 'text/html')
            url = 'tags/' + self.globals['queryTarget'][(self.globals['queryTarget'].find('/tags//')+len('/tags//')):]
            yield self.renderui(['tags'], {'url': url})
        elif self.acceptType == 'text/uri-list':
            def render_file(file):
              subject = self.subject2identifiers(file)[0]
              def render_tagvals(tagdef):
                 home = self.config.home + web.ctx.homepath
                 if tagdef.typestr == 'empty':
                    return home + "/tags/" + subject + "(" + urlquote(tagdef.tagname) + ")\n"
                 elif tagdef.multivalue and file[tagdef.tagname]:
                    return home + "/tags/" + subject + "(" + urlquote(tagdef.tagname ) + "=" + ','.join([urlquote(str(val)) for val in file[tagdef.tagname]]) + ")\n"
                 elif file[tagdef.tagname]:
                    return home + "/tags/" + subject + "(" + urlquote(tagdef.tagname) + "=" + urlquote(str(file[tagdef.tagname])) + ")\n"
                 else:
                    return ''
              return ''.join([ render_tagvals(tagdef) for tagdef in all or [] ])
            
            self.header('Content-Type', 'text/uri-list')
            self.globals['str'] = str 
            yield ''.join([ render_file(file) for file in files or [] ])
        elif self.acceptType == 'application/x-www-form-urlencoded':
            self.header('Content-Type', 'application/x-www-form-urlencoded')
            for file in files:
                body = []
                for tagdef in all:
                    if file[tagdef.tagname]:
                        if tagdef.typestr == 'empty':
                            body.append(urlquote(tagdef.tagname))
                        elif tagdef.multivalue:
                            for val in file[tagdef.tagname]:
                                body.append(urlquote(tagdef.tagname) + '=' + urlquote(val))
                        else:
                            body.append(urlquote(tagdef.tagname) + '=' + urlquote(file[tagdef.tagname]))
                yield '&'.join(body) + '\n'
        elif self.acceptType == 'text/csv':
            self.header('Content-Type', 'text/csv')
            yield ''.join([ res for res in yield_csv(files, [td.tagname for td in all]) ])
        elif self.acceptType == 'application/json':
            self.header('Content-Type', 'application/json')
            yield '['
            pref=''
            for f in files:
                yield pref + f.json + '\n'
                pref=','
            yield ']\n'
        elif self.acceptType == 'text/plain' and len(files) == 1 and len(self.listtags) == 1:
            self.header('Content-Type', 'text/plain')
            val = files[0][self.listtags[0]]
            if type(val) == list:
                yield '\n'.join(val) + '\n'
            else:
                yield '%s\n' % val
                
    def GET(self, uri=None):
        # dispatch variants, browsing and REST
        self.globals['referer'] = self.config['home'] + uri
        try:
            self.view_type = urlunquote(self.storage.view)
        except:
            pass

        self.acceptType = None
        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType in ['text/uri-list',
                              'application/x-www-form-urlencoded',
                              'text/csv',
                              'application/json',
                              'text/plain'
                              'text/html']:
                self.acceptType = acceptType
                break

        if self.acceptType == None:
            self.acceptType = 'text/html'

        for r in self.dbtransact(self.get_body, self.get_postCommit):
            yield r


    def PUT(self, uri):
        try:
            content_type = web.ctx.env['CONTENT_TYPE'].lower()
        except:
            content_type = 'text/plain'

        # we may modify these below...
        subjpreds, listpreds, ordertags = self.path[-1]

        if content_type == 'application/json':
            try:
                rows = jsonArrayFileReader(web.ctx.env['wsgi.input'])
                self.bulk_update_transact(rows, on_missing='abort', on_existing='merge')
            except JSONArrayError:
                et, ev, tb = sys.exc_info()
                web.debug('got exception "%s" parsing JSON input from client' % str(ev),
                          traceback.format_exception(et, ev, tb))
                raise BadRequest(self, 'Invalid input to bulk PUT of tags.')
                
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

            for tag, vals in tagvals.items():
                listpreds.append( web.Storage(tag=tag,op='=', vals=vals) )

        # engage special patterned update mode using 'id' as correlation and False as subjects_iter to signal a path-based subjects query
        subjpreds.append( web.Storage(tag='id', op=None, vals=[]) )
        self.bulk_update_transact(False, on_missing='abort', on_existing='merge')
        web.ctx.status = '204 No Content'
        return ''

    def delete_body(self):
        self.bulk_delete_tags()
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
            self.PUT(uri)
            return self.post_postCommit(None)
        elif action == 'delete':
            return self.dbtransact(self.delete_body, self.post_postCommit)
        else:
            raise BadRequest(self, data="Form field action=%s not understood." % action)

class Query (Node):
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
            self.set_http_etag(txid=self.select_predlist_path_txid(path, versions=self.versions, limit=self.limit))
            #self.txlog('TRACE', value='Query::body txid computed')
            cached = self.http_is_cached()

            if cached:
                web.ctx.status = '304 Not Modified'
                return None
            elif contentType == 'application/json':
                self.txlog('QUERY', dataset=path_linearize(self.path))
                self.queryopts['range'] = self.query_range
                files = self.select_files_by_predlist_path(path=path, versions=self.versions, limit=self.limit, offset=self.offset, json=True)
                self.queryopts['range'] = None
                #self.txlog('TRACE', value='Query::body query returned')
                return files                
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
                yield "\n".join([ "%s/file/%s" % (self.config.home + web.ctx.homepath, self.subject2identifiers(file)[0]) for file in files])
                return
            elif contentType == 'text/csv':
                self.header('Content-Type', 'text/csv')
                for res in yield_csv(files, self.listtags):
                    yield res
                return
            elif contentType == 'application/json':
                self.header('Content-Type', 'application/json')
                yield '['
                pref=''
                for res in files:
                    yield pref + res.json + '\n'
                    pref = ','
                yield ']\n'
                return
            else:
                if self.query_range:
                    raise BadRequest(self, 'Query option "range" not supported for text/html result format.')
                self.header('Content-Type', 'text/html')
                yield self.renderui(['query'], self.globals['querypath'], self.globals['basepath'])
                return

        for res in self.dbtransact(body, postCommit):
            yield res

        #self.log('TRACE', value='Query::GET exiting')

class UI (Node):
    """Represents a generic template for the user interface"""

    def __init__(self, parser, appname, uiopts, path=[], queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        self.uiopts = uiopts
        self.path = path
        self.queryopts = queryopts
        
    def GET(self, uri):
        def body():
            path, self.listtags, writetags, self.limit, self.offset, self.versions = \
                  self.prepare_path_query(self.path,
                                          list_priority=['path', 'list', 'view', 'default'],
                                          list_prefix='file',
                                          extra_tags=[ ])
            self.basepath = path_linearize(path[0:-1])
            self.querypath = [ dict(spreds=[dict(s) for s in spreds],
                                               lpreds=[dict(l) for l in lpreds],
                                               otags=otags)
                                          for spreds, lpreds, otags in path ]
            return None

        def postCommit(files):
            self.uiopts = {}
            self.uiopts['basepath'] = self.basepath
            self.uiopts['querypath'] = self.querypath
            return jsonWriter(self.uiopts)

        return self.dbtransact(body, postCommit)
    
