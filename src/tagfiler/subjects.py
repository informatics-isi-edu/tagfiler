

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
import traceback
import sys

import os
import web
import subprocess
import tempfile
import random
import re
import sys
import time
import datetime
import pytz

from dataserv_app import Application, NotFound, BadRequest, Conflict, RuntimeError, Forbidden, urlquote, urlunquote, parseBoolString, predlist_linearize, path_linearize, wraptag, jsonFileReader, jsonArrayFileReader, JSONArrayError, jsonWriter, getParamEnv, make_temporary_file, yieldBytes

myrand = random.Random()
myrand.seed(os.getpid())


class SubjectCache (object):

    purge_interval_seconds = 60
    cache_stale_seconds = 300

    def __init__(self):
        # entries['%s %s' % (role, querypath)] = (ctime, value)
        self.querypath_entries = dict()
        self.last_purge_time = None

    def purge(self):
        now = datetime.datetime.now(pytz.timezone('UTC'))
        if self.last_purge_time and (now - self.last_purge_time).seconds < SubjectCache.purge_interval_seconds:
            pass
        else:
            self.last_purge_time = now
            for item in self.querypath_entries.items():
                key, entry = item
                ctime, subject = entry
                if (now - ctime).seconds > SubjectCache.cache_stale_seconds:
                    self.querypath_entries.pop(key, None)

    def select(self, db, searchfunc, querypath, role):
        key = '%s %s' % (role, querypath)

        self.purge()
        
        def cached():
            ctime, subject = self.querypath_entries.get(key, (None, None))
            if subject:
                results = db.query('SELECT value AS mtime FROM %s' % wraptag('subject last tagged')
                                   + ' WHERE subject = $id', vars=dict(id=subject.id))
                if len(results) == 1:
                    mtime = results[0].mtime
                    
                    if mtime <= ctime:
                        return subject
                        
                self.querypath_entries.pop(key, None)

            return None

        cached_subject = cached()

        if cached_subject:
            return [ cached_subject ]
        else:
            ctime = datetime.datetime.now(pytz.timezone('UTC'))
            subjects = searchfunc()

            if len(subjects) == 1:
                self.querypath_entries[key] = (ctime, subjects[0])

            return subjects

subject_cache = SubjectCache()

class Node (Application):
    """Abstract AST node for all URI patterns"""

    __slots__ = [ 'appname' ]

    def __init__(self, parser, appname, catalog_id, queryopts=None):
        self.appname = appname
        Application.__init__(self, catalog_id, parser, queryopts)

    def uri2referer(self, uri):
        return self.config['home'] + uri

class Subject (Node):
    """Basic subject CRUD

    Handle subject CRUD operations including awareness of file bodies, excluding actual file I/O.
    """

    def __init__(self, parser=None, appname=None, catalog_id=None, path=None, queryopts=None):
        Node.__init__(self, parser, appname, catalog_id, queryopts)
        self.api = 'subject'
        self.action = None
        self.key = None
        self.dtype = None
        self.file = None
        self.bytes = None
        self.referer = None
        self.update = False
        self.subject = None
        self.name = None
        self.mergeSubjpredsTags = False
        self.path = path
        if len(self.path) == 0:
            self.path = [ ( [], [], [] ) ]
        

    def populate_subject_cached(self, enforce_read_authz=True, allow_blank=False, allow_multiple=False, enforce_parent=False):

        def searchfunc():
            self.populate_subject(enforce_read_authz, allow_blank, allow_multiple, enforce_parent)
            return (self.subjects, self.path_txid)

        subjpreds, listpreds, ordertags = self.path[-1]
        self.unique = self.validate_subjpreds_unique(subjpreds=subjpreds)
        
        if self.unique != None:
            self.subjects, self.path_txid = subject_cache.select(self.db, searchfunc, path_linearize(self.path), self.context.client)
            self.subject = self.subjects[0]
            self.datapred, self.dataid, self.dataname, self.dtype = self.subject2identifiers(self.subject)
        else:
            self.populate_subject(enforce_read_authz, allow_blank, allow_multiple, enforce_parent)
            

    def populate_subject(self, enforce_read_authz=True, allow_blank=False, allow_multiple=False, enforce_parent=False, post_method=False):
        if len(self.path) == 0:
            self.path = [ ( [], [], [] ) ]

        subjpreds, listpreds, ordertags = self.path[-1]

        if len(listpreds) > 0:
            if len(listpreds) == 1 \
               and listpreds[0].tag == 'file' and not listpreds[0].op:
                # we accept (file) listpred as a special disambiguator case for forward-compatibility
                pass
            raise BadRequest(self, 'FileIO module does not support general subject tag list "%s".' % predlist_linearize(listpreds))
        
        self.unique = self.validate_subjpreds_unique(acceptBlank=allow_blank, subjpreds=subjpreds)

        listpreds = [ web.Storage(tag=tag,op=None,vals=[])
                      for tag in ['id', 'content-type', 'bytes', 'modified', 'modified by', 'incomplete']
                      + [ tagdef.tagname for tagdef in self.tagdefsdict.values() if tagdef.unique ] ]

        querypath = [ x for x in self.path ]

        querypath[-1] = (subjpreds, listpreds, [])

        if enforce_parent and len(self.path) > 1:
            # this is a context requiring the parent path to exist
            results = self.select_files_by_predlist_path(path=querypath[0:-1], enforce_read_authz=enforce_read_authz)
            parent = '/' + '/'.join([ '%s(%s)' % (predlist_linearize(s), predlist_linearize(l)) for s, l, o in self.path[0:-1] ])
            if len(results) != 1:
                raise Conflict(self, 'The parent path "%s" does not resolve to a unique parent.' % parent)

        request = '/' + '/'.join([ '%s(%s)' % (predlist_linearize(s), predlist_linearize(l)) for s, l, o in self.path ])

        if post_method and self.unique == None:
            results = []
        else:
            self.path_txid = self.select_predlist_path_txid(querypath, enforce_read_authz=enforce_read_authz)
            results = self.select_files_by_predlist_path(path=querypath, enforce_read_authz=enforce_read_authz)

        if len(results) == 0:
            raise NotFound(self, 'dataset matching "%s"' % request)
        elif len(results) > 0 and self.unique and post_method:
            raise Conflict(self, 'Cannot POST to existing subject "%s".' % (self.subject2identifiers(results[0])[2]))
        elif len(results) > 1 and not allow_multiple:
            count = len(results)
            names = ['"%s"' % self.subject2identifiers(result)[2] for result in results]
            raise Conflict(self, 'Found %d matching subjects, but this operation only supports 1.' % (count))
        
        self.subjects = [ x for x in results ]
        self.subject = self.subjects[0]

        for s in range(0, len(self.subjects)):
            # get file tag which is 'system' authz model so not included already
            results = self.select_tag_noauthn(self.subjects[s], self.tagdefsdict['file'])
            if len(results) > 0:
                self.subjects[s].file = results[0].value
            else:
                self.subjects[s].file = None
            datapred, dataid, dataname, self.subjects[s].dtype = self.subject2identifiers(self.subjects[s])
            if s == 0:
                self.datapred = datapred
                self.dataid = dataid
                self.dataname = dataname
                self.dtype = self.subjects[s].dtype

    def get_body(self):
        #self.populate_subject(allow_blank=True)
        self.populate_subject_cached(allow_blank=True)
        # read authz implied by finding subject
        return None

    def GET(self, uri, sendBody=True):
        #self.log('TRACE', value='Query::GET() entered')
        # this interface has both REST and form-based functions
        
        contentType = 'application/json'

        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType in [ 'text/uri-list', 'application/json', 'text/csv' ]:
                contentType = acceptType
                break

        if contentType == 'text/csv':
            temporary_file, self.temporary_filename = make_temporary_file('query-result-', self.config['store path'], 'a')
            temporary_file.close()

        def body():
            #self.txlog('TRACE', value='Query::body entered')
            self.http_vary.add('Accept')

            path, self.listtags, writetags, self.limit, self.offset = \
                  self.prepare_path_query(self.path,
                                          list_priority=['path', 'list', 'view', 'default'],
                                          extra_tags=[ ])

            #self.txlog('TRACE', value='Query::body query prepared')
            self.set_http_etag(txid=self.select_predlist_path_txid(path, limit=self.limit))
            #self.txlog('TRACE', value='Query::body txid computed')
            cached = self.http_is_cached()

            if cached:
                web.ctx.status = '304 Not Modified'
                return None
            elif contentType == 'application/json':
                self.queryopts['range'] = self.query_range
                files = self.select_files_by_predlist_path(path=path, limit=self.limit, offset=self.offset, json=True)
                self.queryopts['range'] = None
                #self.txlog('TRACE', value='Query::body query returned')
                return files      
            elif contentType == 'text/csv':
                self.queryopts['range'] = self.query_range
                temporary_file = open(self.temporary_filename, 'wb')
                self.copyto_csv_files_by_predlist_path(temporary_file, path, limit=self.limit, offset=self.offset)
                self.queryopts['range'] = None
                temporary_file.close()
                return False
            else:
                self.queryopts['range'] = self.query_range
                files = [file for file in  self.select_files_by_predlist_path(path=path, limit=self.limit, offset=self.offset) ]
                self.queryopts['range'] = None
                #self.txlog('TRACE', value='Query::body query returned')

                return files

        def postCommit(files):
            self.emit_headers()
            if files == None:
                # caching short cut
                return
            
            #self.log('TRACE', value='Query::body postCommit dispatching on content type')

            if contentType == 'text/uri-list':
                # return raw results for REST client
                if self.query_range:
                    raise BadRequest(self, 'Query option "range" not meaningful for text/uri-list result format.')
                self.header('Content-Type', 'text/uri-list')
                response = "\n".join([ "%s/file/%s" % (self.config.homepath, self.subject2identifiers(file)[0]) for file in files]) + '\n'
                self.header('Content-Length', str(len(response)))
                yield response
                return
            elif contentType == 'text/csv':
                try:
                    f = open(self.temporary_filename, 'rb')

                    try:
                        f.seek(0, 2)
                        length = f.tell()

                        self.header('Content-Type', 'text/csv')
                        self.header('Content-Length', str(length))

                        for buf in yieldBytes(f, 0, length-1, self.config['chunk bytes']):
                            yield buf

                    finally:
                        f.close()

                finally:
                    os.remove(self.temporary_filename)

                return
            else:
                self.header('Content-Type', 'application/json')
                yield '['
                pref=''
                for res in files:
                    yield pref + res.json + '\n'
                    pref = ','
                yield ']\n'
                return

        if sendBody:
            for res in self.dbtransact(body, postCommit):
                yield res

    def HEAD(self, uri):
        return self.GET(uri, sendBody=False)

    def delete_body(self):
        spreds, lpreds, otags = self.path[-1]
        
        self.unique = self.validate_subjpreds_unique(acceptBlank=True, subjpreds=spreds)

        results = [ r for r in self.bulk_delete_subjects(self.path) ]

        #self.log('TRACE', value='after deleting subjects')

        if bool(getParamEnv('log bulk details', False)):
            for r in results:
                self.txlog('DELETE', dataset='id=%d' % r.id)

        #self.log('TRACE', value='after txlogging delete of subjects')

        return results

    def delete_postCommit(self, results, set_status=True):
        for r in results:
            if r.file != None:
                filename = self.config['store path'] + '/' + r.file
                dir = os.path.dirname(filename)
                self.deleteFile(filename)
        if set_status:
            web.ctx.status = '204 No Content'
        return ''

    def DELETE(self, uri):
        def body():
            return self.delete_body()
        def postCommit(result):
            return self.delete_postCommit(result)
        return self.dbtransact(body, postCommit)

    def insertForStore_contentType(self, newfile):
        """Extension point for revising content-type metadata..."""
        if self.subject:
            return self.subject.get('content-type', None)
        else:
            return newfile.get('content-type', None)
    
    def insertForStore(self, allow_blank=False, post_method=False):
        """Create or update a catalog subject w/ or w/o file body..."""
        content_type = None
        junk_files = []

        newfile = web.Storage()
        newfile.bytes = self.bytes
        newfile.name = self.name
        newfile.dtype = self.dtype
        newfile.file = self.file
        # don't blindly trust DB data from earlier transactions... do a fresh lookup
        self.mergeSubjpredsTags = False
        status = web.ctx.status
        try:
            self.populate_subject(allow_blank=allow_blank, enforce_parent=True, post_method=post_method)
            if not self.subject.writeok:
                raise Forbidden(self, 'write to file "%s"' % path_linearize(self.path))
                
        except NotFound:
            web.ctx.status = status
            self.subject = None
            self.update = False
            # this is a new dataset independent of others
            if len( set(self.config['file write users']).intersection(set(self.context.attributes).union(set('*'))) ) == 0:
                raise Forbidden(self, 'creation of datasets')
            # raise exception if subjpreds invalid for creating objects
            self.unique = self.validate_subjpreds_unique(acceptBlank=allow_blank, restrictSchema=True, subjpreds=self.path[-1][0])
            self.mergeSubjpredsTags = True

        # determine content_type with extensible callout for subtypes
        content_type = self.insertForStore_contentType(newfile)

        if self.subject:
            # this is the case where we update an existing uniquely tagged file in place
            self.txlog('UPDATE', dataset=path_linearize(self.path))
            newfile.id = None
            if self.subject.file:
                junk_files.append(self.subject.file)
            if newfile.file:
                self.set_tag(self.subject, self.tagdefsdict['file'], newfile.file)
            elif self.subject.file:
                self.delete_tag(self.subject, self.tagdefsdict['file'])
        else:
            # anybody is free to insert new file
            self.txlog('CREATE', dataset=path_linearize(self.path))
            #web.debug(self.file)
            newfile.id = self.insert_file(newfile.file)

        if newfile.id != None:
            newfile.owner=self.context.client
            newfile.writeok=True
            newfile.incomplete=False
        
        newfile['content-type'] = content_type
        
        self.updateFileTags(newfile, self.subject)

        self.subject = newfile
        return junk_files

    def updateFileTags(self, newfile, basefile):
        if not basefile:
            # set initial tags on all new, independent objects
            self.set_tag(newfile, self.tagdefsdict['owner'], newfile.owner)
            self.set_tag(newfile, self.tagdefsdict['created'], 'now')

        if not basefile or self.context.client != basefile['modified by'] or basefile.id != newfile.id:
            self.set_tag(newfile, self.tagdefsdict['modified by'], self.context.client)

        # show virtual tags in inverse mapping too
        self.set_tag(newfile, self.tagdefsdict['tags present'], ['id', 'readok', 'writeok', 'tags present'])

        now = datetime.datetime.now(pytz.timezone('UTC'))
        maxage = myrand.uniform(3, 8)

        if not basefile or not basefile['modified'] or (now - basefile.modified).seconds > maxage or basefile.id != newfile.id:
            self.set_tag(newfile, self.tagdefsdict['modified'], 'now')

        if newfile.dtype == 'file':
            if newfile.bytes != None and (not basefile or newfile.bytes != basefile.bytes or basefile.id != newfile.id):
                self.set_tag(newfile, self.tagdefsdict['bytes'], newfile.bytes)
                
            if newfile.name != None and (not basefile or newfile.name != basefile.name or basefile.id != newfile.id):
                self.set_tag(newfile, self.tagdefsdict['name'], newfile.name)
                
            if newfile['content-type'] and (not basefile or basefile['content-type'] != newfile['content-type'] or basefile.id != newfile.id):
                self.set_tag(newfile, self.tagdefsdict['content-type'], newfile['content-type'])
        elif newfile.dtype in [ None ]:
            if basefile and basefile.bytes != None and basefile.id == newfile.id:
                self.delete_tag(newfile, self.tagdefsdict['bytes'])
            if basefile and basefile['content-type'] != None and basefile.id == newfile.id:
                self.delete_tag(newfile, self.tagdefsdict['content-type'])
            if self.key:
                if basefile:
                    self.delete_tag(basefile, self.tagdefsdict['key'], self.key)
                self.set_tag(newfile, self.tagdefsdict['key'], self.key)

        # try to apply tags provided by user as PUT/POST queryopts in URL
        #    and tags constrained in subjpreds (only if creating new independent object)
        # they all must work to complete transaction
        tagvals = [ (k, [v]) for k, v in self.queryopts.items() ]

        if self.mergeSubjpredsTags:
            tagvals = tagvals + [ (pred.tag, pred.vals) for pred in self.path[-1][0] if pred.op in [ '=', None ] ]

        for tagname, values in tagvals:
            tagdef = self.tagdefsdict.get(tagname, None)
            if tagdef == None:
                raise NotFound(self, 'tagdef="%s"' % tagname)
            self.enforce_tag_authz('write', newfile, tagdef)
            if tagdef.dbtype == '':
                self.set_tag(newfile, tagdef)
            else:
                for value in values:
                    self.set_tag(newfile, tagdef, value)
            self.txlog('SET', dataset=self.subject2identifiers(newfile)[0], tag=tagname, value=values)

        if not basefile and not newfile['incomplete']:
            # only remap on newly created files, when the user has not guarded for chunked upload
            self.doPolicyRule(newfile)

    def deleteFile(self, filename):
        dir = os.path.dirname(filename)
        os.unlink(filename)

        while dir != self.config['store path'] and len(os.listdir(dir)) == 0:
            basedir = dir
            dir = os.path.dirname(basedir)
            try:
                os.rmdir(basedir)
            except:
                pass
            
    def deletePrevious(self, files):
        for file in files:
            self.deleteFile(self.config['store path'] + '/' + file)

    def put_preWriteBody_result(self):
        """Extension point for returning writables in subtypes..."""
        return None

    def put_preWriteBody(self, post_method=False):
        status = web.ctx.status
        try:
            if not post_method:
                self.populate_subject_cached(enforce_read_authz=False, allow_blank=post_method)
            else:
                self.populate_subject(enforce_read_authz=False, allow_blank=post_method, post_method=post_method)
            if not self.subject.readok:
                raise Forbidden(self, 'access to file "%s"' % path_linearize(self.path))
            if not self.subject.writeok: 
                raise Forbidden(self, 'write to file "%s"' % self.subject2identifiers(self.subject)[0])
            return self.put_preWriteBody_result()
                
        except NotFound:
            web.ctx.status = status
            self.subject = None
            
            if len(self.path) == 0:
                self.path = [ ( [], [], [] ) ]
            
            subjpreds, listpreds, ordertags = self.path[-1]
            
            # not found and not unique, treat as new file put
            if len( set(self.config['file write users']).intersection(set(self.context.attributes).union(set('*'))) ) == 0:
                raise Forbidden(self, 'creation of datasets')
            # raise exception if subjpreds invalid for creating objects
            self.unique = self.validate_subjpreds_unique(acceptBlank=True, restrictSchema=True)
            self.mergeSubjpredsTags = True

        return None

    def put_prepareRequest(self):
        # this work happens exactly once per web request, consuming input
        inf = web.ctx.env['wsgi.input']
        try:
            clen = int(web.ctx.env['CONTENT_LENGTH'])
        except:
            clen = None
            # raise LengthRequired()  # if we want to be picky

        try:
            content_range = web.ctx.env['HTTP_CONTENT_RANGE']
            units, rstr = content_range.strip().split(" ")
            rstr, lenstr = rstr.split("/")
            if lenstr == '*':
                flen = None
            else:
                flen = int(lenstr)
            cfirst, clast = rstr.split("-")
            cfirst = int(cfirst)
            clast = int(clast)

            if clen != None:
                if clast - cfirst + 1 != clen:
                    raise BadRequest(self, data='Range: %s does not match content-length %s.' % (content_range, clen))
            else:
                clen = clast - cfirst + 1

        except KeyError:
            flen = clen
            cfirst = 0
            clast = None
            content_range = None

        # at this point we have these data:
        # clen -- content length (body of PUT)
        # flen -- file length (if asserted by PUT Range: header)
        # cfirst -- first byte position of content body in file
        # clast  -- last byte position of content body in file

        if cfirst != None and clast:
            # try update-in-place if user is doing Range: partial PUT
            self.update = True
        else:
            self.update = False

        return (cfirst, clast, clen, flen, content_range)

    def put_postWriteBody(self, post_method=False):
        # this may repeat in case of database races
        if self.mustInsert:
            try:
                self.client_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            except:
                self.client_content_type = None
            return self.insertForStore(allow_blank=(post_method), post_method=post_method)
        else:
            # simplified path for in-place updates
            self.subject = self.subject_prewrite
            newfile = web.Storage(self.subject)
            newfile.bytes = self.bytes
            self.updateFileTags(newfile, self.subject)
            return []

    def put_postWritePostCommit(self, junk_files):
        if not self.partial_content and junk_files:
            self.deletePrevious(junk_files)
        uri = self.config.homepath + '/' + self.api + '/' + self.subject2identifiers(self.subject)[0]
        self.header('Location', uri)
        if self.subject_prewrite == None or self.subject.id != self.subject_prewrite.id:
            web.ctx.status = '201 Created'
            res = uri + '\n'
        else:
            web.ctx.status = '204 No Content'
            res = ''
        return res

    def PUT(self, uri, post_method=False):
        self.uri = uri
        """process file content PUT from client"""
        cfirst, clast, clen, flen, self.partial_content = self.put_prepareRequest()

        content_type = web.ctx.env.get('CONTENT_TYPE', "").lower()

        if self.partial_content:
            raise BadRequest(self, 'PUT of subjects does not support Content-Range partial content.')

        if content_type:
            # remove any charset for the following check
            content_type = content_type.split(";", 1)[0].strip() 
            if content_type == 'application/json':
                try:
                    rows = jsonArrayFileReader(web.ctx.env['wsgi.input'])
                    self.bulk_update_transact(rows, on_missing='create', on_existing='merge')
                except JSONArrayError:
                    et, ev, tb = sys.exc_info()
                    web.debug('got exception "%s" parsing JSON input from client' % str(ev),
                              traceback.format_exception(et, ev, tb))
                    raise BadRequest(self, 'Invalid JSON input to bulk PUT of subjects.')
                
                web.ctx.status = '204 No Content'
                return ''

            elif content_type == 'text/csv':
                csvfp = web.ctx.env['wsgi.input']
                self.bulk_update_transact(csvfp, on_missing='create', on_existing='merge')

                web.ctx.status = '204 No Content'
                return ''

            else:
                raise BadRequest(self, 'Unsupported subject PUT content-type "%s"' % content_type)

        else:
            # do single REST PUT of one subject
            result = self.dbtransact(lambda : self.put_preWriteBody(),
                                 lambda result : result)

            self.subject_prewrite = self.subject
            self.mustInsert = True

            # we get here if write is not disallowed
 
            self.bytes = flen

            return self.dbtransact(lambda : self.put_postWriteBody(post_method=post_method),
                                   lambda result : self.put_postWritePostCommit(result))

    def POST(self, uri):
        """emulate a PUT for browser users with simple form POST"""
        # return same result page as for GET app/tags/subjpreds for convenience

        def putPostCommit(junk_files):
            if junk_files:
                self.deletePrevious(junk_files)
            view = ''
            try:
                view = '?view=%s' % urlquote('%s' % self.subject['default view'])
            except:
                pass
            if view == '' and self.subject.dtype:
                view = '?view=%s' % urlquote('%s' % self.subject.dtype)
            acceptType = self.preferredType()
            url = self.config.homepath + '/' + self.api + '/' + self.subject2identifiers(self.subject)[0]
            self.header('Location', url)
            if acceptType == 'application/json':
                self.header('Content-Type', 'application/json')
                return jsonWriter(self.subject)
            else:
                self.header('Content-Type', 'text/uri-list')
                web.ctx.status = '201 Created'
                return '%s\n' % url

        def deleteBody():
            return self.delete_body()

        def deletePostCommit(result):
            return self.delete_postCommit(result)

        def preDeleteBody():
            self.populate_subject(allow_blank=True, allow_multiple=True)
            if not self.subject.writeok:
                raise Forbidden(self, 'delete of dataset "%s"' % path_linearize(self.path))
            
            ftype = self.subject.dtype
                
            if not ftype:
                ftype = 'blank'
                
            return ftype

        contentType = web.ctx.env.get('CONTENT_TYPE', '').lower()
        if contentType[0:33] == 'application/x-www-form-urlencoded':
            storage = web.input()

            def get_param(param, default=None):
                """get params from any of web.input(), self.queryopts, self.storage"""
                try:
                    value = storage[param]
                except:
                    value = None
                if value == None:
                    value = self.storage.get(param)
                    if value == None:
                        value = self.queryopts.get(param)
                        if value == None:
                            return default
                    else:
                        return unquote(value)
                return value

            self.key = get_param('key')
            self.action = get_param('action')
            if self.action == None:
                raise BadRequest(self, 'Form field "action" is required.')

            if self.action in [ 'put', 'putsq' , 'post' ]:
                # we only support non-file PUT and POST simulation this way
                self.dtype = None
                       
                return self.dbtransact(lambda : self.insertForStore(allow_blank=True, post_method=True),
                                       putPostCommit)

            else:
                raise BadRequest(self, data="Form field action=%s not understood." % self.action)

        else:
            # any unrecognized input type is ignored, and we just process URI with action=post
            return self.dbtransact(lambda : self.insertForStore(allow_blank=True, post_method=True),
                                   putPostCommit)



