
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
from dataserv_app import CatalogManager, NotFound, BadRequest, Conflict, Forbidden, urlquote, urlunquote, jsonWriter, jsonReader, predlist_linearize, path_linearize, downcast_value, jsonArrayFileReader, JSONArrayError, make_temporary_file, yieldBytes
from rest_fileio import FileIO
import subjects
from subjects import Node
import datetime
import StringIO
import psycopg2
import psycopg2.extensions

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

    def __init__(self, parser, appname, catalog_id, queryopts={}):
        Node.__init__(self, parser, appname, catalog_id, queryopts)

    def GET(self, uri):
        
        def body():
            # TODO: is there any db introspection to do here?
            return None
        
        def postCommit(bodyresults):
            self.header('Content-Type', 'application/json')
            descriptor = jsonWriter({
                    'service': 'tagfiler',
                    # TODO: add some API version info?
                    'help': """This is the top-level of a Tagfiler metadata catalog service. The set of API URLs described here can be used by RESTful clients to interact with the service.""",
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
                    },
                                    indent=2) + '\n'
            self.header('Content-Length', str(len(descriptor)))
            return descriptor

        return self.dbtransact(body, postCommit)

class Maintenance(Node):
    def __init__(self, parser, appname, catalog_id, queryopts={}):
        Node.__init__(self, parser, appname, catalog_id, queryopts)

    def PUT(self, uri):
        if self.config.admin not in self.context.attributes:
            raise Forbidden(self, 'maintenance')

        def db_body(db):
            self.db = db
            return None

        # don't use normal dbtransact because vacuum isn't allowed there
        self._db_wrapper(db_body)

        self.db._db_cursor().connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        if downcast_value('boolean', self.queryopts.get('cluster', False)):
            self.dbquery('CLUSTER')
        if downcast_value('boolean', self.queryopts.get('vacuum', False)):
            if downcast_value('boolean', self.queryopts.get('analyze', False)):
                self.dbquery('VACUUM ANALYZE')
            else:
                self.dbquery('VACUUM')
        elif downcast_value('boolean', self.queryopts.get('analyze', False)):
            self.dbquery('ANALYZE')

        self.db._db_cursor().connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

        web.ctx.status = '204 No Content'
        return ''

class CNode (CatalogManager):
    """Abstract AST node for all URI patterns"""

    __slots__ = [ 'appname' ]

    def __init__(self, parser, appname, catalog_id, queryopts=None):
        CatalogManager.__init__(self, parser, appname, catalog_id, queryopts)

    def uri2referer(self, uri):
        return self.config['home'] + uri

class Catalog (CNode):
    """Represents a catalog / URI

       GET    -- returns a listing of catalogs
       POST   -- creates a catalog
       DELETE -- deletes a catalog
    """

    def __init__(self, parser, appname, queryopts={}, catalog_id=None):
        CNode.__init__(self, parser, appname, catalog_id, queryopts)
        try:
            if catalog_id:
                self.catalog_id = int(catalog_id)
            else:
                self.catalog_id = None
        except ValueError:
            raise BadRequest(self, 'Bad catalog id.')


    def GET(self, uri):
        
        def body():
            catalogs = self.select_catalogs(catalog_id=self.catalog_id, 
                        attrs=self.context.attributes, admin=self.config.admin)
            
            if self.catalog_id:
                if not catalogs or not len(catalogs):
                    raise NotFound(self, uri)
                return catalogs[0]
            else:
                return catalogs
        
        def postCommit(bodyresults):
            self.header('Content-Type', 'application/json')
            catalogs = jsonWriter(bodyresults, indent=2) + '\n'
            self.header('Content-Length', str(len(catalogs)))
            return catalogs

        return self.dbtransact(body, postCommit)


    def POST(self, uri):
        
        # Check if user can create catalogs
        if (self.context.attributes | CatalogManager.ANONYMOUS).isdisjoint(self.config['create_catalog_users']):
            raise Forbidden(self, 'catalog')

        # Only accept application/json
        try:
            content_type = web.ctx.env['CONTENT_TYPE'].lower()
        except:
            content_type = 'text/plain'

        if content_type.split(';')[0] != ('application/json'):
            raise BadRequest(self, ('Content type (%s) not supported.' % content_type))

        # Might be worth getting the data now, before we're in the dbtransact call
        input = web.data()

        def body():
            try:
                if input and len(input) > 0:
                    catalog = jsonReader(input)
                else:
                    catalog = dict()
                return self.create_catalog(catalog)
            
            except ValueError, msg:
                raise BadRequest(self, 'Invalid json input to POST catalog: %s' % msg)

            return catalog

        def postCommit(catalog):
            web.ctx.status = '201 Created'
            uri = self.get_homepath(self.get_home(), catalog['id'])
            self.header('Location', uri)
            self.header('Content-Type', 'application/json')
            catalog = jsonWriter(catalog, indent=2) + '\n'
            self.header('Content-Length', str(len(catalog)))
            return catalog

        return self.dbtransact(body, postCommit)


    def DELETE(self, uri):
        
        if not self.catalog_id:
            raise BadRequest(self, 'Catalog id must be specified')

        def body():
            # First, get the catalog. This implicitly tests the read_users
            # ACL, which influences how we respond if the owner test fails.
            # I.e., reader but not owner --> Forbidden
            #       not reader --> NotFound (don't reveal catalog exists
            catalogs = self.select_catalogs(catalog_id=self.catalog_id, 
                                             acl_list='read_users', 
                                             attrs=self.context.attributes, 
                                             admin=self.config.admin)
            if not catalogs or not len(catalogs):
                raise NotFound(self, uri)
            else:
                config = catalogs[0].get('config')
                if config.get('owner') not in self.context.attributes:
                    raise Forbidden(self, uri)
            
            self.delete_catalog(self.catalog_id)
        
        def postCommit(results):
            self.emit_headers()
            web.ctx.status = '204 No Content'
            return ''

        return self.dbtransact(body, postCommit)


class CatalogConfig (CNode):
    """Represents a catalog/ID/config[/name] URI

       GET    -- returns the catalog configuration
       PUT    -- set a named property
       DELETE -- delete a named property
    """

    def __init__(self, parser, appname, catalog_id=None, prop_name=None, prop_val=None, queryopts={}):
        CNode.__init__(self, parser, appname, catalog_id, queryopts)
        self.prop_name = prop_name
        self.prop_val  = prop_val
        try:
            if catalog_id:
                self.catalog_id = int(catalog_id)
            else:
                self.catalog_id = None
        except ValueError:
            raise BadRequest(self, 'Bad catalog id.')
        
        
    def GET(self, uri):
        
        if self.prop_val:
            raise BadRequest(self, 'Cannot get a property by value.')
        
        def body():
            catalogs = self.select_catalogs(catalog_id=self.catalog_id, 
                                            acl_list='read_users', 
                                            attrs=self.context.attributes, 
                                            admin=self.config.admin)
            
            if not catalogs or not len(catalogs):
                raise NotFound(self, 'catalog')
            
            config = catalogs[0]['config']
            if not self.prop_name:
                return config
            else:
                return config.get(self.prop_name,'')
        
        def postCommit(bodyresults):
            self.header('Content-Type', 'application/json')
            bodyresults = jsonWriter(bodyresults, indent=2) + '\n'
            self.header('Content-Length', str(len(bodyresults)))
            return bodyresults

        return self.dbtransact(body, postCommit)
        
        
    def PUT(self, uri):
        
        if not self.prop_name:
            raise BadRequest(self, 'Catalog property name must be specified')

        def body():

            # Get property value
            if self.prop_val:
                overwrite = False
                prop_val = self.prop_val
            else:
                overwrite = True
                try:
                    data = web.data()
                    if data and len(data):
                        prop_val = jsonReader(data)
                    else:
                        prop_val = ''
                except ValueError, msg:
                    raise BadRequest(self, 'Malformed JSON document: %s' % msg)
            # Get catalog, test acls later
            catalogs = self.select_catalogs(catalog_id=self.catalog_id, 
                                             acl_list=None, 
                                             attrs=self.context.attributes, 
                                             admin=self.config.admin)
            if not catalogs or not len(catalogs):
                raise NotFound(self, uri)
            
            catalog  = catalogs[0]
            config   = catalog.get('config')
            writers  = catalog.get(self.CONFIG_WRITE_USERS, list())
            readers  = catalog.get(self.CONFIG_READ_USERS, list())
            attrs    = self.context.attributes | self.ANONYMOUS
            owner    = config.get(self.CONFIG_OWNER)
            is_owner = owner in self.context.attributes
            
            # Test permission to write to properties
            if (not is_owner and attrs.isdisjoint(writers)):
                if attrs.isdisjoint(readers):
                    raise NotFound(self, uri)
                else:
                    raise Forbidden(self, uri)
            
            # Validate property name
            if self.prop_name not in self.CONFIG_ALL:
                raise BadRequest(self, 'Property not supported')
            
            # Validate owner
            if self.prop_name == self.CONFIG_OWNER:
                if not is_owner:
                    raise Forbidden(self, uri)
                if not prop_val or not len(prop_val):
                    raise BadRequest(self, 'Owner must not be blank.')
                if prop_val in self.ANONYMOUS:
                    raise BadRequest(self, 'Owner must not be anonymous.')
            
            # Validate ACL updates
            if self.prop_name in self.CONFIG_ACL:
                if not prop_val or not len(prop_val):
                    prop_val = list()
                elif isinstance(prop_val, str):
                    prop_val = [prop_val]
                elif not isinstance(prop_val, list):
                    raise BadRequest(self, 'Bad input type. Must be list or string value.')
            else:
                # All others must be strings
                if not isinstance(prop_val, str):
                    raise BadRequest(self, 'Bad input type. Must be string value.')
            
            # Update property value
            if (overwrite or
                self.prop_name not in config or
                not isinstance(prop_val, list)):
                # Must overwrite if,
                #  a. value given in uri
                #  b. property not in config already
                #  c. property is immutable
                config[self.prop_name] = prop_val
            else:
                # Merge existing and provided lists
                #  ...it's okay if current val is None
                newval = set(prop_val) | set(config[self.prop_name] or list())
                config[self.prop_name] = list(newval)
            
            # Update the catalog configuration in the registry
            self.update_catalog(catalog)
        
        def postCommit(results):
            self.emit_headers()
            web.ctx.status = '204 No Content'
            return ''

        return self.dbtransact(body, postCommit)
        
        
    def DELETE(self, uri):
        
        def body():
            # Get catalog, test acls later
            catalogs = self.select_catalogs(catalog_id=self.catalog_id, 
                                             acl_list=None, 
                                             attrs=self.context.attributes, 
                                             admin=self.config.admin)
            if not catalogs or len(catalogs):
                raise NotFound(self, uri)
            
            catalog  = catalogs[0]
            config   = catalog.get('config')
            writers  = catalog.get(self.CONFIG_WRITE_USERS, list())
            readers  = catalog.get(self.CONFIG_READ_USERS, list())
            attrs    = self.context.attributes | self.ANONYMOUS
            owner    = config.get(self.CONFIG_OWNER)
            is_owner = owner in self.context.attributes
            
            # Test permission to write to properties
            if (not is_owner and attrs.isdisjoint(writers)):
                if attrs.isdisjoint(readers):
                    raise NotFound(self, uri)
                else:
                    raise Forbidden(self, uri)
            
            # Validate property in supported set
            if self.prop_name not in self.CONFIG_ALL:
                raise BadRequest(self, 'Property not supported.')
            
            # Validate property not 'owner'
            if self.prop_name == self.CONFIG_OWNER:
                raise BadRequest(self, 'Cannot delete owner.')
            
            # Delete value and update catalog, if property is in config
            if self.prop_name in config:
                # Test if this operation is a mutable delete
                if not (self.prop_val and len(self.prop_val) and
                        self.prop_name in self.CONFIG_ACL):
                    # Simply delete if prop is not mutable
                    del config[self.prop_name]
                else:
                    # Remove value from list, if mutable
                    currval = config[self.prop_name]
                    if self.prop_val in currval:
                        currval.remove(self.prop_val)
                # Update registry
                self.update_catalog(catalog)
        
        def postCommit(bodyresults):
            self.emit_headers()
            web.ctx.status = '204 No Content'
            return ''

        return self.dbtransact(body, postCommit)


class FileId(FileIO):
    """Represents a direct FILE/subjpreds URI

       Just creates filename and lets FileIO do the work.

    """
    def __init__(self, parser, appname, catalog_id, path, queryopts={}, storage=None):
        FileIO.__init__(self, parser, appname, catalog_id, path, queryopts)
        self.path = [ ( e[0], e[1], [] ) for e in path ]
        if storage:
            self.storage = storage

class Subject(subjects.Subject):
    def __init__(self, parser, appname, catalog_id, path, queryopts={}, storage=None):
        subjects.Subject.__init__(self, parser, appname, catalog_id, path, queryopts)
        if storage:
            self.storage = storage

class Tagdef (Node):
    """Represents TAGDEF/ URIs"""

    def __init__(self, parser, appname, catalog_id, tag_id=None, queryopts={}):
        Node.__init__(self, parser, appname, catalog_id, queryopts)
        self.tag_id = tag_id
        self.writepolicy = None
        self.readpolicy = None
        self.multivalue = None
        self.is_unique = None
        self.action = None
        self.dbtype = None
        self.tagref = None
        self.softtagref = None
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
            tagdef = self.tagdefsdict.get(self.tag_id, None)
            if tagdef == None:
                raise NotFound(self, data='tag definition %s' % (self.tag_id))
            self.enforce_tagdef_authz('write', tagdef)
            self.delete_tagdef(tagdef)
            return None

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

        if self.tagref is None:
            try:
                self.tagref = self.queryopts['tagref']
            except:
                pass

        if self.softtagref is None:
            try:
                self.softtagref = downcast_value('boolean', self.queryopts['soft'])
            except:
                self.softtagref = False

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
            result = self.insert_tagdef()
            return result

        def postCommit(results):
            web.ctx.status = '201 Created'
            web.header('Content-Type', 'application/json')
            response = jsonWriter(results) + '\n'
            web.header('Content-Length', str(len(response)))
            return response

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/subjpreds and TAGS/subjpreds/tagvals URIs"""

    def __init__(self, parser, appname, catalog_id, path=None, queryopts={}):
        Node.__init__(self, parser, appname, catalog_id, queryopts)
        if path:
            self.path = path
        else:
            self.path = [ ([], [], []) ]

    def get_body(self):
        subjpreds, listpreds, otags = self.path[-1]

        self.path_modified, self.listtags, writetags, self.limit, self.offset = \
              self.prepare_path_query(self.path,
                                      list_priority=['path', 'list', 'view', 'subject', 'all'],
                                      extra_tags=[ ])

        self.http_vary.add('Accept')
        self.set_http_etag(self.select_predlist_path_txid(self.path_modified))
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return None, None
        
        self.txlog('GET TAGS', dataset=path_linearize(self.path_modified))

        all = [ tagdef for tagdef in self.tagdefsdict.values() if tagdef.tagname in self.listtags ]
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

        if self.acceptType == 'text/plain':
            if len(files) > 1:
                raise Conflict(self, 'Multiple matching subjects conflict with returning tag value as plain text.')

            td = self.tagdefsdict.get(listpreds[0].tag)
            if td and td.multivalue:
                raise Conflict(self, 'Multivalue tagdef conflicts with returning tag value as plain text.')
            # td is None will be error-handled by the query engine itself
            self.plain_tag = td

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
                 home = self.config.homepath
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
        elif self.acceptType == 'text/plain':
            self.header('Content-Type', 'text/plain')
            
            yield files[0].get(self.plain_tag.tagname)
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
                              'text/plain']:
                self.acceptType = acceptType
                break

        if self.acceptType == None:
            self.acceptType = 'application/json'

        if self.acceptType == 'text/csv':
            temporary_file, self.temporary_filename = make_temporary_file('query-result-', self.config['store path'], 'a')
            temporary_file.close()

        if self.acceptType == 'text/plain':
            subjpreds, listpreds, otags = self.path[-1]
            if len(listpreds) != 1:
                raise Conflict(self, 'Query returning %d tags conflicts with returning tag value as plain text.', len(listpreds))

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

        elif content_type[0:33] == 'application/x-www-form-urlencoded':
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

        elif content_type == 'text/plain' and len(listpreds) == 1 and listpreds[0].op == None:
            # treat request body as a single tag value
            content = web.ctx.env['wsgi.input'].read()
            listpreds.append( web.Storage(tag=listpreds[0].tag, op='=', vals=[ content ]) )

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


