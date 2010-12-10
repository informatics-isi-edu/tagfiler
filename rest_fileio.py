import traceback
import sys

import os
import web
import subprocess
import tempfile
import random
import re
import traceback
import sys

from dataserv_app import Application, NotFound, BadRequest, Conflict, RuntimeError, urlquote, parseBoolString

# build a map of mime type --> primary suffix
mime_types_suffixes = dict()
f = open('/etc/mime.types', 'rb')
for line in f.readlines():
    m = re.match(r'^(?P<type>[^ \t]+)[ \t]+(?P<exts>.+)', line)
    if m:
        g = m.groupdict()
        mime_types_suffixes[g['type']] = g['exts'].split(' ')[0]
f.close()

# we want .txt not .asc!
mime_types_suffixes['text/plain'] = 'txt'

def yieldBytes(f, first, last, chunkbytes):
    """Helper function yields range of file."""
    f.seek(first, 0)  # first from beginning (os.SEEK_SET)
    byte = first
    while byte <= last:
        readbytes = min(chunkbytes, last - byte + 1)
        buf = f.read(readbytes)

        byte += len(buf)
        yield buf

        if len(buf) < readbytes:
            break

def choose_content_type(clientval, guessedval, taggedval):
    """Hueristic choice between client-supplied and guessed Content-Type.

       TODO: expand this with practical experience of bogus browser
           values and abnormal guessed values."""
    def basetype(typestr):
        if typestr:
            return typestr.split(';')[0]
        else:
            return None

    bclientval = basetype(clientval)
    bguessedval = basetype(guessedval)
    btaggedval = basetype(taggedval)
    
    if bclientval in [ 'application/octet-stream' ]:
        clientval = None
        bclientval = None

    if taggedval:
        if btaggedval in [ bclientval, bguessedval ]:
            return taggedval
        elif bguessedval == bclientval:
            return guessedval
        return taggedval
    else:
        if clientval:
            return clientval
    return guessedval

class FileIO (Application):
    """Basic bulk file I/O

    These handler functions attempt to do buffered I/O to handle
    arbitrarily large file sizes without requiring arbitrarily large
    memory allocations.

    """
    __slots__ = [ 'formHeaders', 'action', 'filetype', 'bytes', 'client_content_type', 'referer' ]

    def __init__(self):
        Application.__init__(self)
        self.action = None
        self.filetype = 'file'
        self.bytes = None
        self.referer = None
        self.update = False
        self.needed_db_globals = []  # turn off expensive db queries we ignore

    def GETfile(self, uri, sendBody=True):
        global mime_types_suffixes

        def body():
            #web.debug(self.data_id, self.version)
            results = self.select_files_by_predlist(data_id=self.data_id, version=self.version, listtags=['content-type'])
            if len(results) == 0:
                if self.version == None:
                    raise NotFound('dataset "%s"' % self.data_id)
                else:
                    raise NotFound('dataset "%s"@%d' % (self.data_id, self.version))
            file = results[0]
            self.enforce_file_authz('read', self.data_id, self.version)
            self.version = file.version
            #web.debug(file)
            return (file, file['content-type'])

        def postCommit(result):
            # if the dataset is a remote URL, just redirect client
            result, content_type = result
            if not result.local:
                opts = [ '%s=%s' % (opt[0], urlquote(opt[1])) for opt in self.queryopts.iteritems() ]
                if len(opts) > 0:
                    querystr = '&'.join(opts)
                    if len(result.location.split("?")) > 1:
                        querystr = '&' + querystr
                    else:
                        querystr = '?' + querystr
                else:
                    querystr = ''
                raise web.seeother(result.location + querystr)
            else:
                self.location = result.location
                filename = self.store_path + '/' + self.location
                try:
                    f = open(filename, "rb")
                    if content_type == None:
                        p = subprocess.Popen(['/usr/bin/file', '-i', '-b', filename], stdout=subprocess.PIPE)
                        line = p.stdout.readline()
                        content_type = line.strip()
                    return (f, content_type)
                except:
                    # this may happen sporadically under race condition:
                    # query found unique file, but someone replaced it before we opened it
                    return (None, None)

        count = 0
        limit = 10
        f = None
        while not f:
            count = count + 1
            if count > limit:
                # we failed after too many tries, just give up
                # if this happens in practice, need to investigate or redesign...
                raise web.internallerror('Could not access local copy of ' + self.data_id)

            # we do this in a loop to compensate for race conditions noted above
            f, content_type = self.dbtransact(body, postCommit)

        # we only get here if we were able to both:
        #   a. open the file for reading its content
        #   b. obtain its content-type from /usr/bin/file test

        # fix up some ugliness in CentOS 'file -i -b' outputs
        content_type = re.sub('application/x-zip', 'application/zip', content_type)
        
        mime_type = content_type.split(';')[0]
        m = re.match(r'^.+\.[^.]{1,4}', self.data_id)
        if m:
            disposition_name = self.data_id
        else:
            try:
                suffix = mime_types_suffixes[mime_type]
                disposition_name = self.data_id + '.' + suffix
            except:
                disposition_name = self.data_id
        
        # SEEK_END attribute not supported by Python 2.4
        # f.seek(0, os.SEEK_END)
        f.seek(0, 2)
        length = f.tell()
        # SEEK_SET is not supported by Python 2.4
        # f.seek(0, os.SEEK_SET)
        f.seek(0, 0)

        #web.header('Content-Location', self.globals['homepath'] + '/file/%s@%d' % (urlquote(self.data_id), self.version))
        if sendBody:

            try:
                pass
                #self.db._db_cursor().connection.close()
            except:
                pass

            # parse Range: header if it exists
            rangeset = []
            invalid = False
            try:
                http_range = web.ctx.env['HTTP_RANGE']
                units, set = http_range.split('=')
                for r in set.split(","):
                    try:
                        first, last = r.split("-")
                        if first == '' and last == '':
                            invalid = True
                            break
                        elif first == '':
                            first = length - int(last)
                            last = length - 1
                        elif last == '':
                            first = int(first)
                            last = length - 1
                        else:
                            first = int(first)
                            last = int(last)

                        if last < first:
                            invalid = True
                            break
                    
                        if first >= length:
                            break

                        if first < 0:
                            first = 0

                        if last >= length:
                            last = length - 1

                        rangeset.append((first, last))
                    except:
                        pass
            except:
                rangeset = None

            self.log('GET', dataset=self.data_id)
            if rangeset != None:

                if len(rangeset) == 0:
                    # range not satisfiable
                    web.ctx.status = '416 Requested Range Not Satisfiable'
                    web.header("Content-Range", "bytes */%s" % length)
                    return
                elif len(rangeset) == 1:
                    # result is a single Content-Range body
                    first, last = rangeset[0]
                    web.ctx.status = '206 Partial Content'
                    web.header('Content-Length', last - first + 1)
                    web.header('Content-Range', "bytes %s-%s/%s" % (first, last, length))
                    web.header('Content-Type', content_type)
                    web.header('Content-Disposition', 'attachment; filename="%s"' % (disposition_name))
                    for res in yieldBytes(f, first, last, self.chunkbytes):
                        self.midDispatch()
                        yield res
                else:
                    # result is a multipart/byteranges ?
                    boundary = "%s%s%s" % (random.randrange(0, 0xFFFFFFFFL),
                                           random.randrange(0, 0xFFFFFFFFL),
                                           random.randrange(0, 0xFFFFFFFFL))
                    web.header('Content-Type', 'multipart/byteranges; boundary=%s' % boundary)

                    for r in range(0,len(rangeset)):
                        first, last = rangeset[r]
                        yield '\r\n--%s\r\nContent-type: %s\r\nContent-range: bytes %s-%s/%s\r\nContent-Disposition: attachment; filename="%s"\r\n\r\n' \
                              % (boundary, content_type, first, last, length, disposition_name)
                        for res in yieldBytes(f, first, last, self.chunkbytes):
                            self.midDispatch()
                            yield res
                        if r == len(rangeset) - 1:
                            yield '\r\n--%s--\r\n' % boundary
                    
            else:
                # result is whole body
                web.ctx.status = '200 OK'
                web.header('Content-type', content_type)
                web.header('Content-Length', length)
                web.header('Content-Disposition', 'attachment; filename="%s"' % (disposition_name))
                
                for buf in yieldBytes(f, 0, length - 1, self.chunkbytes):
                    self.midDispatch()
                    yield buf

        else: # not sendBody...
            # we only send headers (for HTTP HEAD)
            web.header('Content-type', content_type)
            web.header('Content-Length', length)
            pass

        f.close()


    def HEAD(self, uri):
        return self.GETfile(uri, sendBody=False)

    def GET(self, uri):

        storage = web.input()
        suffix = ''
        try:
            self.action = storage.action
            self.filetype = storage.type
        except:
            pass
        
        params = []
        
        try:
            if storage['read users'] == '*':
                params.append('read users=*')
        except:
            pass
        
        try:
            if storage['write users'] == '*':
                params.append('write users=*')
        except:
            pass
        
        if len(params) > 0:
            suffix = '?' + '&'.join(params)

        if self.action == 'define':

            def body():
                results = self.select_file()
                if len(results) == 0:
                    return None
                self.enforce_file_authz('write', local=results[0].local)
                return None

            def postCommit(results):
                if self.filetype == 'file':
                    return self.renderlist("Upload data file",
                                           [self.render.FileForm(suffix)])
                elif self.filetype == 'url':
                    return self.renderlist("Register a remote URL",
                                           [self.render.UrlForm(suffix)])
                else:
                    raise BadRequest(data='Unexpected dataset type "%s"' % self.filetype)

            return self.dbtransact(body, postCommit)
        else:
            return self.GETfile(uri)

    def DELETE(self, uri):

        def body():
            results = self.select_file()
            if len(results) == 0:
                if self.version == None:
                    raise NotFound('dataset "%s"' % self.data_id)
                else:
                    raise NotFound('dataset "%s"@%d' % (self.data_id, self.version))
            file = results[0]
            self.version = file.version
            self.enforce_file_authz('write', file.data_id, file.version, local=file.local)
            self.delete_file()
            self.txlog('DELETE', dataset=self.data_id)
            return result

        def postCommit(result):
            if result.local and result.location != None:
                """delete the file"""
                filename = self.store_path + '/' + result.location
                dir = os.path.dirname(filename)
                self.deleteFile(filename)
                web.ctx.status = '204 No Content'
            return ''

        return self.dbtransact(body, postCommit)

    def scanFormHeader(self, inf):
        """peel off mixed/form-data header and top boundary"""

        # TODO: detect unix-style '\n' and behave appropriately?
        boundary1 = inf.readline()
        boundaryN = '\r\n' + boundary1[0:-2] + '--\r\n'

        self.formHeaders = { }

        inHeaders = True
        while inHeaders:
            buf = web.ctx.env['wsgi.input'].readline()
            if buf == '\r\n':
                # next byte begins file payload
                inHeaders = False
            else:
                parts = buf[0:-2].split(':')
                try:
                    self.formHeaders[parts[0].lower()] = parts[1].strip()
                except:
                    self.formHeaders[parts[0].lower()] = None

        return (boundary1, boundaryN)

    def insertForStore(self):
        """Only call this after writing a full file body!"""
        remote = not self.local
        content_type = None
        results = []
        try:
            # treat full entity PUT to any version as PUT to the head version
            self.version = None
            results = self.select_files_by_predlist(data_id=self.data_id, version=self.version, listtags=['content-type'])
            if len(results) == 0:
                if self.version == None:
                    raise NotFound('dataset "%s"' % self.data_id)
                else:
                    raise NotFound('dataset "%s"@%d' % (self.data_id, self.version))
            file = results[0]
            self.version = file.version
            self.enforce_file_authz('write', self.data_id, file.version)
        except NotFound:
            file = None

        created = False

        if self.bytes != None:
            if file:
                tagged_content_type = file['content-type']
            else:
                tagged_content_type = None

            try:
                filename = self.store_path + '/' + self.location
                p = subprocess.Popen(['/usr/bin/file', '-i', '-b', filename], stdout=subprocess.PIPE)
                line = p.stdout.readline()
                guessed_content_type = line.strip()
            except:
                guessed_content_type = None

            content_type = choose_content_type(self.client_content_type,
                                               guessed_content_type,
                                               tagged_content_type)

        if file:
            # check permissions and update existing file
            self.enforce_file_authz('write', local=file.local)
            # register as a new version of the existing file
            self.version = file.version + 1  # BUG?  PUT to a version other than current head?
            self.insert_file(self.data_id, self.version, self.local, self.location)
            self.txlog('UPDATE', dataset=self.data_id)
        else:
            # anybody is free to insert new uniquely named file
            created = True
            self.txlog('CREATE', dataset=self.data_id)
            self.version = 1
            self.insert_file(self.data_id, self.version, self.local, self.location)

        self.updateFileTags(file, content_type, versionSet=True)

        return results

    def updateFileTags(self, basefile, content_type, versionSet=False):
        if not basefile:
            # set initial tags
            self.set_file_tag('owner', self.authn.role)
            self.set_file_tag('created', 'now')
            self.set_file_tag('name', self.data_id)
        elif self.version != basefile.version:
            # copy basefile tags
            results = self.select_filetags(data_id=basefile.file, version=basefile.version)
            for result in results:
                if result.tagname not in [ 'bytes', 'modified', 'modified by', 'content-type', 'url' ]:
                    tags = self.select_file_tag(result.tagname, data_id=basefile.file, version=basefile.version)
                    for tag in tags:
                        #web.debug('copying /tags/%s@%d/%s=%s' % (basefile.file, basefile.version, result.tagname, tag.value)
                        #          + ' to /tags/%s@%d/%s=%s' % (self.data_id, self.version, result.tagname, tag.value))
                        self.set_file_tag(result.tagname, value=tag.value)
            
        self.set_file_tag('modified by', self.authn.role)
        self.set_file_tag('modified', 'now')

        if self.local:
            self.set_file_tag('bytes', self.bytes)
            self.delete_file_tag('url')
                
            if content_type:
                self.set_file_tag('content-type', content_type)
        else:
            self.delete_file_tag('bytes')
            self.delete_file_tag('content-type')
            self.set_file_tag('url', self.location)

        # try to apply tags provided by user as PUT/POST queryopts in URL
        # they all must work to complete transaction
        for tagname in self.queryopts.keys():
            self.enforce_tag_authz('write', tagname)
            self.set_file_tag(tagname, self.queryopts[tagname])
            self.txlog('SET', dataset=self.data_id, tag=tagname, value=self.queryopts[tagname])

        if not basefile:
            # only remap on newly created files
            srcroles = set(self.remap.keys()).intersection(self.authn.roles)
            if len(srcroles) == 1:
                try:
                    t = self.db.transaction()
                    srcrole = srcroles.pop()
                    dstrole, readusers, writeusers = self.remap[srcrole]
                    for readuser in readusers:
                        self.set_file_tag('read users', readuser, data_id=data_id, version=version)
                        self.txlog('REMAP', dataset=data_id, tag='read users', value=readuser)
                    for writeuser in writeusers:
                        self.set_file_tag('write users', writeuser, data_id=data_id, version=version)
                        self.txlog('REMAP', dataset=data_id, tag='write users', value=writeuser)
                    self.set_file_tag('owner', dstrole, data_id=data_id, version=version)
                    self.txlog('REMAP', dataset=data_id, tag='owner', value=dstrole)
                    t.commit()
                except:
                    #et, ev, tb = sys.exc_info()
                    #web.debug('got exception during owner remap attempt',
                    #          traceback.format_exception(et, ev, tb))
                    t.rollback()
            elif len(srcroles) > 1:
                raise Conflict("Ambiguous remap rules encountered")

    def storeInput(self, inf, f, flen=None, cfirst=None, clen=None):
        """copy content stream"""

        if cfirst != None:
            f.seek(cfirst, 0)

        bytes = 0
        eof = False
        while not eof:
            if clen != None:
                buf = inf.read(min((clen - bytes), self.chunkbytes))
            else:
                buf = inf.read(self.chunkbytes)

            f.write(buf)
            buflen = len(buf)
            bytes = bytes + buflen
            self.midDispatch()

            if clen != None:
                if clen == bytes:
                    eof = True
                elif buflen == 0:
                    f.close()
                    raise BadRequest(data="Only received %s bytes out of expected %s bytes." % (bytes, clen)) # entity undersized
            elif buflen == 0:
                eof = True

        if flen != None:
            f.seek(flen,0)
            f.truncate()
        else:
            f.seek(0,2)
            flen = f.tell()

        #web.debug('stored %d of %d bytes' %( bytes, flen))
        return (bytes, flen)


    def getTemporary(self, mode):
        """get a temporary file"""

        prefix = self.authn.role
        if prefix != None:
            prefix += '-'
        else:
            prefix = 'anonymous-'
            
        dir = self.store_path + '/' + urlquote(self.data_id)

        """posible race condition in mkdir and rmdir"""
        count = 0
        limit = 10
        while True:
            count = count + 1
            try:
                if not os.path.exists(dir):
                    os.makedirs(dir, mode=0755)
        
                fileHandle, filename = tempfile.mkstemp(prefix=prefix, dir=dir)
                os.close(fileHandle)
                f = open(filename, mode)
                break
            except:
                if count > limit:
                    raise
            
        return (f, filename)

    def deleteFile(self, filename):
        dir = os.path.dirname(filename)
        os.unlink(filename)

        if len(os.listdir(dir)) == 0:
            try:
                os.rmdir(dir)
            except:
                pass
            
    def deletePrevious(self, files):
        for file in files:
            if file.local and file.location != None:
                self.deleteFile(self.store_path + '/' + file.location)

    def putPreWriteBody(self):
        try:
            if not self.update:
                # treat full entity PUT to any version as PUT to the head version
                self.version = None
            results = self.select_files_by_predlist(data_id=self.data_id, version=self.version, listtags=['content-type'])
            if len(results) == 0:
                if self.version == None:
                    raise NotFound('dataset "%s"' % self.data_id)
                else:
                    raise NotFound('dataset "%s"@%d' % (self.data_id, self.version))
            file = results[0]
            self.version = file.version
            self.enforce_file_authz('write', self.data_id, file.version)
        except NotFound:
            file = None

        if file:
            if self.update:
                if file.local:
                    if file.location == None:
                        return (None, None)
                    self.location = file.location
                    self.version = file.version
                    filename = self.store_path + '/' + self.location
                    self.local = file.local
                    f = open(filename, 'r+b')
                    self.updateFileTags(file, None)
                    #web.debug('reopen', self.location, self.local, filename, f)
                    return f
                else:
                    raise Conflict(data="The resource %s is a remote URL dataset and so does not support partial byte access." % self.data_id)

        return None

    def PUT(self, uri):
        """store file content from client"""

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
                    raise BadRequest(data='Range: %s does not match content-length %s' % (content_range, clen))
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

        def preWriteBody():
            return self.putPreWriteBody()

        def preWritePostCommit(results):
            return results
        
        if cfirst != None and clast:
            # try update-in-place if user is doing Range: partial PUT
            self.update = True
            self.local = True
            # if checksum is not set, then allow chunk updates
            if len(self.gettagvals('sha256sum')) == 0:
                self.localFilesImmutable = False
        else:
            self.update = False

        # this retries if a file was found but could not be opened due to races
        f = self.dbtransact(preWriteBody, preWritePostCommit)

        try:
            pass
#            self.db._db_cursor().connection.close()
        except:
            pass

        # we get here if write is not disallowed
        if f == None:
            f, filename = self.getTemporary('wb')
            self.location = filename[len(self.store_path)+1:]
            self.local = True
        else:
            filename = None

        # we only get here if we have a file to write into
        wbytes, flen = self.storeInput(inf, f, flen, cfirst, clen)
        f.close()

        self.bytes = flen
        self.wbytes = wbytes

        def postWriteBody():
            # this may repeat in case of database races
            try:
                self.client_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            except:
                self.client_content_type = None

            return self.insertForStore()

        def postWritePostCommit(files):
            if not content_range and files:
                self.deletePrevious(files)
            uri = self.home + self.store_path + '/' + urlquote(self.data_id) + '@%d' % self.version
            web.header('Location', uri)
            if filename:
                web.ctx.status = '201 Created'
                res = uri
            else:
                web.ctx.status = '204 No Content'
                res = ''
            return res

        try:
            if not self.update:
                result = self.dbtransact(postWriteBody, postWritePostCommit)
            else:
                result = postWritePostCommit([])
            return result
        except web.SeeOther:
            raise
        except:
            if filename:
                self.deleteFile(filename)
            raise

    def testAndExpandFiles(self, filesdict, data_id, trigger, set):
        results = self.select_file_tag(trigger, data_id=data_id)
        if len(results) > 0:
            for fname in self.gettagvals(set, data_id=data_id):
                for file in self.select_file(fname):
                    if not filesdict.has_key(file.name):
                        filesdict[file.name] = file

    def POST(self, uri):
        """emulate a PUT for browser users with simple form POST"""
        # return same result page as for GET app/tags/data_id for convenience

        def preWriteBody():
            return self.putPreWriteBody()

        def preWritePostCommit(results):
            f = results
            if f != None:
                raise BadRequest(data='Cannot perform range-based access via POST.')
            return None
        
        def putBody():
            return self.insertForStore()

        def putPostCommit(files):
            if files:
                self.deletePrevious(files)
            raise web.seeother('/tags/%s' % (urlquote(self.data_id)))

        def deleteBody():
            filesdict = dict()
            results = self.select_file()
            if len(results) == 0:
                raise NotFound(data='dataset %s' % (self.data_id))
            result = results[0]
            self.enforce_file_authz('write', local=result.local)
            self.version = result.version
            filesdict[result.name] = result

            self.testAndExpandFiles(filesdict, self.data_id, 'Image Set', 'contains')
            
            for res in filesdict.itervalues():
                self.delete_file(res.name, res.version)
                self.txlog('DELETE', dataset=res.name)
            return filesdict.values()
        
        def deletePostCommit(files):
            self.deletePrevious(files)
            raise web.seeother(self.referer)

        def preDeleteBody():
            results = self.select_file()
            if len(results) == 0:
                raise NotFound(data='dataset %s' % (self.data_id))
            result = results[0]
            self.enforce_file_authz('write', local=result.local)
            if result.local:
                ftype = 'file'
            else:
                try:
                    # custom DEI EIU hack, to proxy delete to all member files
                    results = self.select_file_tag('Image Set')
                    if len(results) > 0:
                        ftype = 'imgset'
                    else:
                        ftype = 'url'
                except:
                    ftype = 'url'
            return ftype

        def preDeletePostCommit(result):
            target = self.home + web.ctx.homepath
            ftype = result
            return self.renderlist("Delete Confirmation",
                                   [self.render.ConfirmForm(ftype)])
        
        contentType = web.ctx.env['CONTENT_TYPE'].lower()
        if contentType[0:19] == 'multipart/form-data':
            # we only support file PUT simulation this way

            # do pre-test of permissions to abort early if possible
            self.dbtransact(preWriteBody, preWritePostCommit)

            inf = web.ctx.env['wsgi.input']
            boundary1, boundaryN = self.scanFormHeader(inf)
            f, tempFileName = self.getTemporary("w+b")

            try:
                self.client_content_type = self.formHeaders['content-type']
            except:
                self.client_content_type = None

            try:
                try:
                    self.db._db_cursor().connection.close()
                except:
                    pass
                wbytes, flen = self.storeInput(inf, f)
        
                # now we have to remove the trailing part boundary we
                # copied to disk by being lazy above...
                # SEEK_END attribute not supported by Python 2.4
                # f.seek(0 - len(boundaryN), os.SEEK_END)
                f.seek(0 - len(boundaryN), 2)
                buf = f.read(len(boundaryN))
                f.seek(0 - len(boundaryN), 2)
                f.truncate() # truncate to current seek location
                bytes = f.tell()
                f.close()
                if buf != boundaryN:
                    # we did not get an entire multipart body apparently
                    raise BadRequest(data="The multipart/form-data terminal boundary was not found.")
                self.location = tempFileName[len(self.store_path)+1:len(tempFileName)]
                self.local = True
                self.bytes = bytes

                result = self.dbtransact(putBody, putPostCommit)
                return result
            except web.SeeOther:
                raise
            except:
                self.deleteFile(tempFileName)
                raise

        elif contentType[0:33] == 'application/x-www-form-urlencoded':
            storage = web.input()
            self.action = storage.action

            try:
                self.referer = storage.referer
            except:
                self.referer = "/file"

            #web.debug(self.referer)

            if self.action == 'delete':
                return self.dbtransact(preDeleteBody, preDeletePostCommit)
            elif self.action == 'CancelDelete':
                raise web.seeother(self.referer)
            elif self.action == 'ConfirmDelete':
                return self.dbtransact(deleteBody, deletePostCommit)
            elif self.action in [ 'put', 'putsq' ]:
                # we only support URL PUT simulation this way
                if self.action == 'put':
                    self.location = storage.url
                elif self.action == 'putsq':
                    # add title=name queryopt for stored queries
                    self.location = storage.url + '?title=%s' % urlquote(self.data_id)
                self.local = False
                return self.dbtransact(putBody, putPostCommit)

            else:
                raise BadRequest(data="Form field action=%s not understood." % self.action)

        else:
            raise BadRequest(data="Content-Type %s not expected via this interface."% contentType)


class LogFileIO (FileIO):

    def __init__(self):
        FileIO.__init__(self)


    def GET(self, uri, sendBody=True):

        if 'admin' not in self.authn.roles:
            raise Forbidden('read access to log file "%s"' % self.data_id)

        if not self.log_path:
            raise Conflict('log_path is not configured on this server')

        if self.queryopts.get('action', None) == 'view':
            disposition_name = None
        else:
            disposition_name = self.data_id

        filename = self.log_path + '/' + self.data_id
        try:
            f = open(filename, "rb")
            
            f.seek(0, 2)
            length = f.tell()
            f.seek(0, 0)

            web.ctx.status = '200 OK'
            if disposition_name:
                web.header('Content-type', "text/plain")
                web.header('Content-Disposition', 'attachment; filename="%s"' % (disposition_name))
                web.header('Content-Length', length)
            else:
                pollmins = 1
                top = "<pre>"
                bottom = "</pre>"
                web.header('Content-type', "text/html")
                web.header('Content-Length', len(top) + length + len(bottom))
                    
            if sendBody:
                if not disposition_name:
                    yield top
                for buf in yieldBytes(f, 0, length - 1, self.chunkbytes):
                    self.midDispatch()
                    yield buf
                if not disposition_name:
                    yield bottom

            f.close()
        
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception in logfileIO',
                      traceback.format_exception(et, ev, tb))
            raise NotFound('log file "%s"' % self.data_id)
