
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
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote, urlunquote, idquote, jsonWriter, parseBoolString, predlist_linearize, path_linearize, downcast_value, jsonFileReader, jsonArrayFileReader, JSONArrayError, make_temporary_file, yieldBytes
from rest_fileio import FileIO
import subjects
from subjects import Node
import datetime
import StringIO

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
            val = '{' + ','.join([wrapval(v) for v in val]) + '}'
        if type(val) not in [ str, unicode ]:
            val = '%s' % val
        return '"' + val.replace('"','""') + '"'

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

class Toplevel (Node):
    """Represents a bare / URI at the top of catalog

       GET   -- gives a listing
    """

    def __init__(self, parser, appname, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        self.globals['view'] = None

    def GET(self, uri):
        
        def body():
            # TODO: is there any db introspection to do here?
            return None
        
        def postCommit(bodyresults):
            self.header('Content-Type', 'application/json')
            descriptor = jsonWriter({
                    'service': 'tagfiler',
                    # TODO: add some API version info?
                    'help': """
This is the top-level of a Tagfiler metadata catalog service. The set
of API URLs described here can be used by RESTful clients to interact
with the service.
""",
                    'apis': [
                        # TODO: make these full URLs?
                        'tagdef',
                        'subject',
                        'file',
                        'tags'
                        ]
                    # TODO: add introspection on supported operators?
                    # TODO: add introspection on supported dbtypes?
                    # TODO: add introspection on configured security/how to authn/authz?
                    })
            return descriptor + '\n'

        return self.dbtransact(body, postCommit)

class FileId(FileIO):
    """Represents a direct FILE/subjpreds URI

       Just creates filename and lets FileIO do the work.

    """
    def __init__(self, parser, appname, path, queryopts={}, storage=None):
        FileIO.__init__(self, parser, appname, path, queryopts)
        self.path = [ ( e[0], e[1], [] ) for e in path ]
        if storage:
            self.storage = storage

class Subject(subjects.Subject):
    def __init__(self, parser, appname, path, queryopts={}, storage=None):
        subjects.Subject.__init__(self, parser, appname, path, queryopts)
        if storage:
            self.storage = storage

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

    def __init__(self, parser, appname, tag_id=None, queryopts={}):
        Node.__init__(self, parser, appname, queryopts)
        self.tag_id = tag_id
        self.writepolicy = None
        self.readpolicy = None
        self.multivalue = None
        self.is_unique = None
        self.action = None
        self.dbtype = None
        self.tagref = None
        self.tagdefs = {}

    def GET(self, uri):

        def body():
            results = self.select_tagdef(self.tag_id)
            if len(results) == 0:
                raise NotFound(self, data='tag definition %s' % (self.tag_id))
            return results

        def postCommit(tagdefs):
            self.emit_headers()
            self.header('Content-Type', 'application/json')
            return jsonWriter(tagdefs) + '\n'

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
            web.ctx.status = '204 No Content'
            return ''

        if len(self.queryopts) > 0:
            raise BadRequest(self, data="Query options are not supported on this interface.")

        return self.dbtransact(body, postCommit)
                
    def PUT(self, uri):

        if self.tag_id == None:
            raise BadRequest(self, data="Tag definitions require a non-empty tag name.")

        # self.writepolicy take precedence over queryopts...

        if self.dbtype is None:
            try:
                self.dbtype = self.queryopts['dbtype']
            except:
                pass

        if self.tagref == None:
            try:
                self.tagref = self.queryopts['tagref']
            except:
                pass

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
            tag_id = downcast_value('text', self.tag_id) # force early validation

            if len( set(self.config['tagdef write users']).intersection(set(self.context.attributes).union(set('*'))) ) == 0:
                raise Forbidden(self, 'creation of tag definitions')
                
            results = self.select_tagdef(self.tag_id, enforce_read_authz=False)
            if len(results) > 0:
                raise Conflict(self, data="Tag %s is already defined." % self.tag_id)
            self.insert_tagdef()
            return None

        def postCommit(results):
            web.ctx.status = '201 Created'
            return ''

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

    def get_body(self):
        self.path_modified, self.listtags, writetags, self.limit, self.offset = \
              self.prepare_path_query(self.path,
                                      list_priority=['path', 'list', 'view', 'subject', 'all'],
                                      extra_tags=
                                      [ 'id', 'file', 'name', 
                                        'write users', 'modified' ] 
                                      + [ tagdef.tagname for tagdef in self.globals['tagdefsdict'].values() if tagdef.unique ])

        self.http_vary.add('Accept')
        self.set_http_etag(self.select_predlist_path_txid(self.path_modified))
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return None, None
        
        self.txlog('GET TAGS', dataset=path_linearize(self.path_modified))

        all = [ tagdef for tagdef in self.globals['tagdefsdict'].values() if tagdef.tagname in self.listtags ]
        all.sort(key=lambda tagdef: tagdef.tagname)

        if self.acceptType == 'application/json':
            files = self.select_files_by_predlist_path(self.path_modified, limit=self.limit, json=True)
        elif self.acceptType == 'text/csv':
            temporary_file = open(self.temporary_filename, 'wb')
            self.copyto_csv_files_by_predlist_path(temporary_file, self.path_modified, limit=self.limit)
            temporary_file.close()
            return (False, all)
        else:
            files = list(self.select_files_by_predlist_path(self.path_modified, limit=self.limit))

        if len(files) == 0:
            raise NotFound(self, 'subject matching "%s"' % predlist_linearize(self.path_modified[-1][0], lambda x: x))

        return (files, all)

    def get_postCommit(self, results):
        files, all = results

        if files == None:
            # caching short-cut
            return
        
        self.emit_headers()
        if self.acceptType == 'text/uri-list':
            def render_file(file):
              subject = self.subject2identifiers(file)[0]
              def render_tagvals(tagdef):
                 home = self.config.home + web.ctx.homepath
                 if tagdef.dbtype == '':
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
                        if tagdef.dbtype == '':
                            body.append(urlquote(tagdef.tagname))
                        elif tagdef.multivalue:
                            for val in file[tagdef.tagname]:
                                body.append(urlquote(tagdef.tagname) + '=' + urlquote(val))
                        else:
                            body.append(urlquote(tagdef.tagname) + '=' + urlquote(file[tagdef.tagname]))
                yield '&'.join(body) + '\n'
        elif self.acceptType == 'text/csv':
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
            for f in files:
                yield pref + f.json + '\n'
                pref=','
            yield ']\n'

                
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
                              'application/json']:
                self.acceptType = acceptType
                break

        if self.acceptType == None:
            self.acceptType = 'application/json'

        if self.acceptType == 'text/csv':
            temporary_file, self.temporary_filename = make_temporary_file('query-result-', self.config['store path'], 'a')
            temporary_file.close()

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

                try:
                    clen = int(web.ctx.env['CONTENT_LENGTH'])
                except:
                    clen = None

                if clen is not None and clen < 1024 * 1024:
                    rows = list(rows)

                self.bulk_update_transact(rows, on_missing='abort', on_existing='merge')
            except JSONArrayError:
                et, ev, tb = sys.exc_info()
                web.debug('got exception "%s" parsing JSON input from client' % str(ev),
                          traceback.format_exception(et, ev, tb))
                raise BadRequest(self, 'Invalid input to bulk PUT of tags.')
                
            web.ctx.status = '204 No Content'
            return ''

        elif content_type == 'text/csv':
            csvfp = web.ctx.env['wsgi.input']

            try:
                clen = int(web.ctx.env['CONTENT_LENGTH'])
            except:
                clen = None

            if clen is not None and clen < 1024 * 1024:
                buf = csvfp.read(min(1024*1024, clen))
                csvfp = StringIO.StringIO(buf)
                rewind = True
            else:
                rewind = False

            self.bulk_update_transact(csvfp, on_missing='abort', on_existing='merge', subject_iter_rewindable=rewind)

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
        web.ctx.status = '204 No Content'
        return ''

    def DELETE(self, uri):
        # RESTful delete of exactly one tag on 1 or more files...
        return self.dbtransact(self.delete_body, self.delete_postCommit)


