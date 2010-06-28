import os
import web
import subprocess
import tempfile
import random
import re

from dataserv_app import Application, NotFound, BadRequest, urlquote

# build a map of mime type --> primary suffix
mime_types_suffixes = dict()
f = open('/etc/mime.types', 'rb')
for line in f.readlines():
    m = re.match(r'^(?P<type>[^ \t]+)[ \t]+(?P<exts>.+)', line)
    if m:
        g = m.groupdict()
        mime_types_suffixes[g['type']] = g['exts'].split(' ')[0]
f.close()

class FileIO (Application):
    """Basic bulk file I/O

    These handler functions attempt to do buffered I/O to handle
    arbitrarily large file sizes without requiring arbitrarily large
    memory allocations.

    """
    __slots__ = [ 'formHeaders', 'action', 'filetype', 'bytes' ]

    def __init__(self):
        Application.__init__(self)
        self.action = None
        self.filetype = 'file'
        self.bytes = None

    def GETfile(self, uri, sendBody=True):
        global mime_types_suffixes

        def body():
            results = self.select_file()
            if len(results) == 0:
                raise NotFound(data='dataset %s' % (self.data_id))
            self.enforceFileRestriction('read users')
            return results[0]

        def postCommit(result):
            # if the dataset is a remote URL, just redirect client
            if not result.local:
                raise web.seeother(result.location)
            else:
                self.location = result.location
                filename = self.store_path + '/' + self.location
                try:
                    f = open(filename, "rb")
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

        def yieldBytes(f, first, last):
            """Helper function yields range of file."""
            f.seek(first, 0)  # first from beginning (os.SEEK_SET)
            byte = first
            while byte <= last:
                readbytes = min(self.chunkbytes, last - byte + 1)
                buf = f.read(readbytes)

                byte += len(buf)
                yield buf
                
                if len(buf) < readbytes:
                    break

        if sendBody:

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
                    for res in yieldBytes(f, first, last):
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
                        for res in yieldBytes(f, first, last):
                            yield res
                        if r == len(rangeset) - 1:
                            yield '\r\n--%s--\r\n' % boundary
                    
            else:
                # result is whole body
                web.header('Content-type', content_type)
                web.header('Content-Length', length)
                web.header('Content-Disposition', 'attachment; filename="%s"' % (disposition_name))
                
                for buf in yieldBytes(f, 0, length - 1):
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
            if storage.restricted.lower() == 'true':
                suffix = '?restricted'
            else:
                suffix = ''
        except:
            pass

        target = self.home + web.ctx.homepath + '/file/' + urlquote(self.data_id) + suffix
        if self.action == 'define' and self.filetype == 'file':
            return self.renderlist("Upload data file",
                                   [self.render.FileForm(target)])
        elif self.action == 'define' and self.filetype == 'url':
            return self.renderlist("Register a remote URL",
                                   [self.render.UrlForm(target)])
        else:
            return self.GETfile(uri)

    def DELETE(self, uri):

        def body():
            results = self.select_file()
            if len(results) == 0:
                raise NotFound(data='dataset %s' % (self.data_id))
            self.enforceFileRestriction('write users')
            self.delete_file()
            return results[0]

        def postCommit(result):
            if result.local:
                """delete the file"""
                filename = self.store_path + '/' + result.location
                dir = os.path.dirname(filename)
                os.unlink(filename)
                
                """delete the directory if empty"""
                if len(os.listdir(dir)) == 0:
                    try:
                        os.rmdir(dir)
                    except:
                        pass
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
                    self.formHeaders[parts[0]] = parts[1].strip()
                except:
                    self.formHeaders[parts[0]] = None

        return (boundary1, boundaryN)

    def insertForStore(self):
        results = [ res for res in self.select_file() ]

        if len(results) > 0:
            # check permissions and update existing file
            try:
                self.enforceFileRestriction('write users')
                self.update_file()
            except e:
                if self.local == True:
                    os.unlink(self.store_path + '/' + self.location)
                raise e
        else:
            # anybody is free to insert new uniquely named file
            self.insert_file()
            t = self.db.transaction()
            try:
                self.set_file_tag('owner', web.ctx.env['REMOTE_USER'])
                t.commit()
            except:
                t.rollback()
    
            t = self.db.transaction()
            try:
                self.set_file_tag('created', 'now')
                t.commit()
            except:
                t.rollback()

            t = self.db.transaction()
            try:
                self.set_file_tag('name', self.data_id)
                t.commit()
            except:
                t.rollback()
    
            t = self.db.transaction()
            try:
                self.set_file_tag('read users', '*')
                t.commit()
            except:
                t.rollback()
    
        t = self.db.transaction()
        try:
            self.set_file_tag('modified by', web.ctx.env['REMOTE_USER'])
            t.commit()
        except:
            t.rollback()

        t = self.db.transaction()
        try:
            self.set_file_tag('modified', 'now')
            t.commit()
        except:
            t.rollback()

        if self.bytes:
            t = self.db.transaction()
            try:
                self.set_file_tag('bytes', self.bytes)
                t.commit()
            except:
                t.rollback()
                
            t = self.db.transaction()
            try:
                self.delete_file_tag('url')
                t.commit()
            except:
                t.rollback()
        else:
            t = self.db.transaction()
            try:
                self.delete_file_tag('bytes')
                t.commit()
            except:
                t.rollback()

            t = self.db.transaction()
            try:
                self.set_file_tag('url', self.location)
                t.commit()
            except:
                t.rollback()
        # try to apply tags provided by user as PUT/POST queryopts in URL
        # they all must work to complete transaction
        for tagname in self.queryopts.keys():
            self.enforceFileTagRestriction(tagname)
            self.set_file_tag(tagname, self.queryopts[tagname])

        return results

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

            if clen != None:
                if clen == bytes:
                    eof = True
                elif buflen == 0:
                    f.close()
                    os.unlink(filename)
                    raise BadRequest(data="Only received %s bytes out of expected %s bytes." % (bytes, clen)) # entity undersized
            elif buflen == 0:
                eof = True

        if flen != None:
            f.seek(flen,0)
            f.truncate()
        else:
            f.seek(0,2)
            flen = f.tell()

        return (bytes, flen)


    def getTemporary(self, mode):
        """get a temporary file"""

        prefix = self.user()
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


    def deletePrevious(self, result):
        if result.local:
            # previous result had local file, so free it
            filename = self.store_path + '/' + result.location
            dir = os.path.dirname(filename)
            os.unlink(filename)

            """delete the directory if empty"""
            if len(os.listdir(dir)) == 0:
                try:
                    os.rmdir(dir)
                except:
                    pass

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

        # at this point we have these data:
        # clen -- content length (body of PUT)
        # flen -- file length (if asserted by PUT Range: header)
        # cfirst -- first byte position of content body in file
        # clast  -- last byte position of content body in file

        def preWriteBody():
            results = self.select_file()
            if len(results) == 0:
                return None
            self.enforceFileRestriction('write users')
            return results[0]

        def preWritePostCommit(result):
            if result != None:
                if not result.local:
                    raise Conflict(data="The resource %s is not a local file." % self.data_id)
                self.location = result.location
                filename = self.store_path + '/' + self.location
                try:
                    f = open(filename, 'r+b')
                    return (f, None)
                except:
                    return (None, None)
            else:
                f, filename = self.getTemporary('wb')
                return (f, filename)
        
        if cfirst and clast:
            # try update-in-place if user is doing Range: partial PUT
            self.update = True
        else:
            self.update = False

        count = 0
        limit = 10
        f = None
        insertFilename = None
        while not f:
            count += 1
            if count > limit:
                raise web.internalerror('Could not access local copy of ' + self.data_id)

            # we do this in a loop in case of select/open race conditions
            f, insertFilename = self.dbtransact(preWriteBody, preWritePostCommit)

        # we only get here if we have a file to write into
        wbytes, flen = self.storeInput(inf, f, flen, cfirst, clen)
        f.close()

        if insertFilename:
            # the file we wrote is new so needs to go into database
            self.location = insertFilename[len(self.store_path)+1:]
            self.local = True
            self.bytes = flen
            self.wbytes = wbytes

            def postWriteBody():
                # this may repeat in case of database races
                return self.insertForStore()

            def postWritePostCommit(results):
                if len(results) > 0:
                    self.deletePrevious(results[0])
                return 'Stored %s bytes' % (self.wbytes)

            return self.dbtransact(postWriteBody, postWritePostCommit)
        else:
            return 'Stored %s bytes' % (wbytes)


    def POST(self, uri):
        """emulate a PUT for browser users with simple form POST"""
        # return same result page as for GET app/tags/data_id for convenience

        def putBody():
            return self.insertForStore()

        def putPostCommit(results):
            if len(results) > 0:
                self.deletePrevious(results[0])
            raise web.seeother('/tags/%s' % (urlquote(self.data_id)))

        def deleteBody():
            results = self.select_file()
            if len(results) == 0:
                raise NotFound(data='dataset %s' % (self.data_id))
            self.enforceFileRestriction('write users')
            self.delete_file()
            return results[0]

        def deletePostCommit(result):
            self.deletePrevious(result)
            raise web.seeother('/file')

        contentType = web.ctx.env['CONTENT_TYPE'].lower()
        if contentType[0:19] == 'multipart/form-data':
            # we only support file PUT simulation this way
            inf = web.ctx.env['wsgi.input']
            boundary1, boundaryN = self.scanFormHeader(inf)
            f, tempFileName = self.getTemporary("w+b")
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
                os.unlink(tempFileName)
                raise BadRequest(data="The multipart/form-data terminal boundary was not found.")
            self.location = tempFileName[len(self.store_path)+1:len(tempFileName)]
            self.local = True
            self.bytes = bytes

            return self.dbtransact(putBody, putPostCommit)

        elif contentType[0:33] == 'application/x-www-form-urlencoded':
            storage = web.input()
            self.action = storage.action

            if self.action == 'delete':
                target = self.home + web.ctx.homepath
                return self.renderlist("Delete Confirmation",
                                   [self.render.ConfirmForm(target, 'file', self.data_id, urlquote)])
            elif self.action == 'CancelDelete':
                raise web.seeother('/file')
            elif self.action == 'ConfirmDelete':
                return self.dbtransact(deleteBody, deletePostCommit)
            elif self.action == 'put':
                # we only support URL PUT simulation this way
                self.location = storage.url
                self.local = False
                return self.dbtransact(putBody, putPostCommit)

            else:
                raise BadRequest(data="Form field action=%s not understood." % self.action)

        else:
            raise BadRequest(data="Content-Type %s not expected via this interface."% contentType)
