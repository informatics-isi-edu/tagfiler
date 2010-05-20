# define abstract syntax tree nodes for more readable code

import web
from dataserv_app import Application, NotFound
from rest_fileio import FileIO
from browse_form import FormIO, FileList, FileVersionList, TagForm, FileTags, HasTags

class Node (object):
    __slots__ = [ 'appname' ]
    def __init__(self, appname):
        self.appname = appname

class Files (Node, FileList):
    """Represents a bare FILE/ URI"""
    __slots__ = []
    def __init__(self, appname):
        Node.__init__(self, appname)
        FileList.__init__(self)

class History (Node, FileVersionList):
    """Represents a VERSION/data_id URI"""
    __slots__ = [ 'data_id']
    def __init__(self, appname, data_id):
        Node.__init__(self, appname)
        FileVersionList.__init__(self)
        self.data_id = data_id

class FileIdVers (Node, FileIO):
    """Represents a direct FILE/data_id/vers_id URI

       Just creates filename and lets FileIO do the work.

       A form POST also populates self.formHeaders with raw data from browser...

    """
    __slots__ = [ 'data_id', 'vers_id' ]
    def __init__(self, appname, data_id, vers_id=None):
        Node.__init__(self, appname)
        FileIO.__init__(self)
        self.data_id = data_id
        self.vers_id = vers_id

    def makeFilename(self):
        return "%s/%s/%s" % (self.store_path, self.data_id, self.vers_id)

class FormId (Node, FormIO):
    """Represents UPLOAD/data_id form URI

       Just creates captures data_id and lets FormIO do the work.

       A form POST also populates self.formHeaders with raw data from browser...

    """
    __slots__ = [ 'data_id' ]
    def __init__(self, appname, data_id=None):
        Node.__init__(self, appname)
        FormIO.__init__(self)
        self.data_id = data_id

class Tagdef (Node, TagForm):
    __slots__ = [ 'tag_id', 'typestr' ]
    def __init__(self, appname, tag_id=None, typestr=None):
        Node.__init__(self, appname)
        TagForm.__init__(self)
        self.tag_id = tag_id
        self.typestr = typestr

class Tags (Node, FileTags):
    __slots__ = [ 'data_id', 'tag_id', 'value' ]
    def __init__(self, appname, data_id, tag_id='', value=''):
        Node.__init__(self, appname)
        FileTags.__init__(self)
        self.data_id = data_id
        self.tag_id = tag_id
        self.value = value

class Query (Node, HasTags):
    __slots__ = [ 'tagnames', 'queryopts' ]
    def __init__(self, appname, tagnames=[], queryopts={}):
        Node.__init__(self, appname)
        HasTags.__init__(self)
        self.tagnames = set(tagnames)
        self.queryopts = queryopts

