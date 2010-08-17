# define abstract syntax tree nodes for more readable code

import web
import urllib
import re
from dataserv_app import Application, NotFound, BadRequest, Conflict, Forbidden, urlquote
from rest_fileio import FileIO

def listmax(list):
    if len(list) > 0:
        return max(list)
    else:
        return 0
        
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
            results = self.select_tagdef(tagname='list on homepage')
            if len(results) > 0:
                self.predlist = [ { 'tag' : 'list on homepage', 'op' : None, 'vals' : [] } ]
            else:
                self.predlist=[]
            return [ (res.file,
                      self.test_file_authz('write', owner=res.owner, data_id=res.file) )
                      for res in self.select_files_by_predlist() ]

        def postCommit(results):
            target = self.home + web.ctx.homepath
            files = results
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
            readers = storage.readers
            writers = storage.writers
        except:
            raise BadRequest(data="Missing one of the required form fields (name, filetype).")

        if name == '':
            raise BadRequest(data="The form field name must not be empty.")
        else:
            raise web.seeother(self.home + web.ctx.homepath + '/file/' + urlquote(name) 
                               + '?type=' + urlquote(filetype) + '&action=define' 
                               + '&read users=' + urlquote(readers) + '&write users=' + urlquote(writers))
        

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
            predefined, userdefined = tagdefs
            return self.renderlist("Tag definitions",
                                   [self.render.TagdefExisting(self.target, predefined, self.typenames, 'System', lambda mode, tag: self.test_tagdef_authz(mode, tag), urlquote),
                                    self.render.TagdefExisting(self.target, userdefined, self.typenames, 'User', lambda mode, tag: self.test_tagdef_authz(mode, tag), urlquote),
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
                        typestr = storage['type-%s' % (key[4:])]
                        readpolicy = storage['readpolicy-%s' % (key[4:])]
                        writepolicy = storage['writepolicy-%s' % (key[4:])]
                        multivalue = storage['multivalue-%s' % (key[4:])]
                        self.tagdefs[storage[key]] = (typestr, readpolicy, writepolicy, multivalue)
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
                                       [self.render.ConfirmForm(self.home + web.ctx.homepath, 'tagdef', self.tag_id, urlquote)])
            else:
                # send client back to get form page again
                raise web.seeother('/tagdef')

        return self.dbtransact(body, postCommit)

class FileTags (Node):
    """Represents TAGS/data_id URIs"""

    __slots__ = [ 'data_id', 'tag_id', 'value', 'tagvals' ]

    def __init__(self, appname, data_id=None, tag_id='', value=None, tagvals=None):
        Node.__init__(self, appname)
        self.data_id = data_id
        self.tag_id = tag_id
        self.value = value
        self.apptarget = self.home + web.ctx.homepath
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
        return values

    def get_tag_postCommit(self, values):
        web.header('Content-Type', 'application/x-www-form-urlencoded')
        if len(values) > 0:
            return "&".join([(urlquote(self.tag_id) + '=' + urlquote(self.mystr(val))) for val in values])
        else:
            return urlquote(self.tag_id)

    def buildtaginfo(self, where1, where2):
        owner = self.owner()
        tagdefs = [ (tagdef.tagname,
                     tagdef.typestr,
                     self.test_tag_authz('write', tagdef.tagname, fowner=owner))
                    for tagdef in self.select_tagdef(where=where1, order='tagname') ]
        tagdefsdict = dict([ (tagdef[0], tagdef) for tagdef in tagdefs ])
        filetags = [ (result.file, result.tagname) for result in self.select_filetags(where=where2) ]
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

        return (self.buildtaginfo('owner is null', ' tagdefs.owner is null'),         # system
                self.buildtaginfo('owner is not null', ' tagdefs.owner is not null'), # userdefined
                self.buildtaginfo('', '') )                                           # all

    def get_title_one(self):
        return 'Tags for dataset "%s"' % self.data_id

    def get_title_all(self):
        return 'Tags for all datasets'

    def get_all_html_render(self, results):
        system, userdefined, all = results
        if self.data_id:
            return self.renderlist(self.get_title_one(),
                                   [self.render.FileTagExisting('System', self.apptarget, 'tags', self.data_id, system, urlquote),
                                    self.render.FileTagExisting('User', self.apptarget, 'tags', self.data_id, userdefined, urlquote),
                                    self.render.FileTagNew('Set tag values', self.apptarget, 'tags', self.data_id, self.typenames, all, urlquote),
                                    self.render.TagdefNewShortcut('Define more tags', self.apptarget)])
        else:
            return self.renderlist(self.get_title_all(),
                                   [self.render.FileTagValExisting('', self.apptarget, 'tags', self.data_id, all, urlquote)])       

    def get_all_postCommit(self, results):
        system, userdefined, all = results
        all = ( all[0], all[1], all[2], all[3], all[4],
                max(system[5], userdefined[5]) ) # use maximum length for user input boxes

        for acceptType in self.acceptTypesPreferedOrder():
            if acceptType == 'text/uri-list':
                target = self.home + web.ctx.homepath
                return self.render.FileTagUriList(target, all, urlquote)
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
        keys = self.tagvals.keys()
        if len(keys) == 1:
            self.tag_id = keys[0]
            vals = self.tagvals[self.tag_id]
            if len(vals) == 1:
                self.value = vals[0]
            elif len(vals) > 1:
                web.debug(self.tagvals)
                raise BadRequest(data="GET does not support multiple values in the URI.")
            return self.GETtag(uri)
        elif len(keys) > 1:
            web.debug(self.tagvals)
            raise BadRequest(data="GET does not support multiple tag names in the URI.")
        else:
            return self.GETall(uri)

    def put_body(self):
        for tag_id in self.tagvals.keys():
            results = self.select_tagdef(tag_id)
            if len(results) == 0:
                raise NotFound(data='tag definition %s' % tag_id)
            self.enforce_tag_authz('write', tag_id)
            for value in self.tagvals[tag_id]:
                self.set_file_tag(tag_id, value)
            self.log('SET', dataset=self.data_id, tag=tag_id)
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
        self.enforce_tag_authz('write')
        self.delete_file_tag(self.tag_id, self.value)
        return None

    def delete_postCommit(self, results):
        self.log('DELETE', dataset=self.data_id, tag=self.tag_id)
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
        return None

    def post_putBody(self):
        for tag_id in self.tagvals:
            self.enforce_tag_authz('write', tag_id)
            self.set_file_tag(tag_id, self.tagvals[tag_id])
            self.log('SET', dataset=self.data_id, tag=tag_id)
        return None

    def post_deleteBody(self):
        self.enforce_tag_authz('write')
        self.delete_file_tag(self.tag_id, self.value)
        self.log('DELETE', dataset=self.data_id, tag=self.tag_id)
        return None

    def post_postCommit(self, results):
        url = '/tags/' + urlquote(self.data_id)
        raise web.seeother(url)

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
                return self.dbtransact(self.post_putBody, self.post_postCommit)
            else:
                return self.dbtransact(self.post_nullBody, self.post_postCommit)
        elif action == 'delete':
            return self.dbtransact(self.post_deleteBody, self.post_postCommit)
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
        user = self.user()
        acldefs = [ ('readers', 'text', tagdef.owner == user and tagdef.readpolicy == 'tag'),
                    ('writers', 'text', tagdef.owner == user and tagdef.writepolicy == 'tag') ]
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
                 aclinfo )

    def get_title_one(self):
        return 'ACLs for tag "%s"' % self.data_id

    def get_title_all(self):
        return 'ACLs for all tags'

    def get_all_html_render(self, results):
        system, userdefined, all = results
        if self.data_id:
            return self.renderlist(self.get_title_one(),
                                   [self.render.FileTagExisting('', self.apptarget, 'tagdefacl', self.data_id, all, urlquote),
                                    self.render.FileTagNew('Add an authorized user', self.apptarget, 'tagdefacl', self.data_id, self.typenames, all, urlquote)])
        else:
            return self.renderlist(self.get_title_all(),
                                   [self.render.FileTagValExisting('', self.apptarget, 'tagdefacl', self.data_id, all, urlquote)])       

    def put_body(self):
        """Override FileTags.put_body to consult tagdef ACL instead"""
        self.enforce_tagdef_authz('write', tag_id=self.data_id)
        for acl in self.tagvals.keys():
            for value in self.tagvals[acl]:
                self.set_tag_acl(dict(writers='write', readers='read')[acl],
                                 value, self.data_id)
                self.log('SET', tag=self.data_id, mode=acl, user=value)
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
            self.log('SET', tag=self.data_id, mode=tag_id, user=self.tagvals[tag_id])
        return None

    def post_deleteBody(self):
        self.enforce_tagdef_authz('write', tag_id=self.data_id)
        self.delete_tag_acl(dict(writers='write', readers='read')[self.tag_id],
                            self.value, self.data_id)
        self.log('DELETE', tag=self.data_id, mode=self.tag_id, user=self.value)
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
                files = [ (res.file,
                           self.test_file_authz('write', owner=res.owner, data_id=res.file) )
                          for res in self.select_files_by_predlist() ]
            else:
                files = []
            alltags = [ tagdef.tagname for tagdef in self.select_tagdef(order='tagname') ]
            return ( files, alltags )

        def postCommit(results):
            files, alltags = results
            target = self.home + web.ctx.homepath
            apptarget = self.home + web.ctx.homepath

            if self.action in set(['add', 'delete']):
                raise web.seeother(self.qtarget() + '?action=edit')

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
