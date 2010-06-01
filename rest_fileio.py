import os
import web
import subprocess

from dataserv_app import Application, NotFound, urlquote

class FileIO (Application):
    """Basic bulk file I/O

    These handler functions attempt to do buffered I/O to handle
    arbitrarily large file sizes without requiring arbitrarily large
    memory allocations.

    """
    __slots__ = [ 'formHeaders', 'action', 'filetype' ]

    def __init__(self):
        Application.__init__(self)
        self.action = None
        self.filetype = 'file'

    def makeFilename(self):
        return ''

    def GETfile(self, uri):

        def body():
            if self.vers_id == None:
                self.vers_id = self.select_file_version_max()
            if self.vers_id == None:
                raise NotFound()
            else:
                results = self.select_file_version()
                if len(results) == 0:
                    raise NotFound()
                return results[0]

        def postCommit(result):
            # if the dataset is a remote URL, just redirect client
            if result.url:
                raise web.seeother(result.url)

        # we only get here if the dataset is a locally stored file

        self.dbtransact(body, postCommit)

        # need to yield outside postCommit as a generator func
        filename = self.makeFilename()
        f = open(filename, "rb")

        p = subprocess.Popen(['/usr/bin/file', filename], stdout=subprocess.PIPE)
        line = p.stdout.readline()
        p.kill()
        web.header('Content-type', line.split(':')[1].strip())
        
        #web.header('Content-type','text/html')
        #web.header('Transfer-Encoding','chunked')

        # SEEK_END attribute not supported by Python 2.4
        # f.seek(0, os.SEEK_END)
        f.seek(0, 2)
        length = f.tell()
        f.seek(0, os.SEEK_SET)

        # report length so browsers can show progress bar
        web.header('Content-Length', length)
        web.header('Content-Disposition', 'attachment; filename="%s"' % (self.data_id))

        bytes = 0
        while bytes < length:
            buf = f.read(self.chunkbytes)

            # don't exceed reported length, even if file changed under us
            if (bytes + len(buf)) <= length:
                bytes += len(buf)
            else:
                buf = buf[0:length - bytes]
                bytes = length

            # Note, it seems one cannot yield from inside a try block!
            yield buf

        f.close()

    def GET(self, uri):

        storage = web.input()

        try:
            self.action = storage.action
            self.filetype = storage.type
        except:
            pass

        target = self.home + web.ctx.homepath + '/file/' + urlquote(self.data_id)
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
            if self.vers_id == None:
                raise NotFound()
            results = self.select_file_version()
            if len(results) == 0:
                raise NotFound()
            self.delete_file_version()
            return results[0]

        def postCommit(result):
            if result.url == None:
                filename = self.makeFilename()
                os.unlink(filename)
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

        # disallow update to a specific version of the file
        if self.vers_id != None:
            raise web.BadRequest()

        currentVersion = self.select_file_version_max()
        if currentVersion == None:
            self.vers_id = 1
        else:
            self.vers_id = currentVersion + 1
        self.insert_file_version()
        if self.vers_id == 1:
            try:
                self.set_file_tag('owner', web.ctx.env['REMOTE_USER'])
            except:
                pass
        try:
            self.set_file_tag('last modified by', web.ctx.env['REMOTE_USER'])
        except:
            pass
        try:
            self.set_file_tag('last modified', 'now')
        except:
            pass
        return True

    def storeInput(self, inf):
        """copy content stream"""

        filename = self.makeFilename()
        f = None

        p = os.path.dirname(filename)

        if not os.path.exists(p):
            os.makedirs(p, mode=0755)
        f = open(filename, "wb")

        eof = False
        while not eof:
            buf = inf.read(self.chunkbytes)
            if len(buf) == 0:
                eof = True
            f.write(buf)

        return f


    def PUT(self, uri):
        """store file content from client"""
        def body():
            self.insertForStore()
            return None

        def postCommit(results):
            f = self.storeInput(web.ctx.env['wsgi.input'])
            bytes = f.tell()
            f.close()
            return 'Stored %s bytes' % (bytes)

        return self.dbtransact(body, postCommit)


    def POST(self, uri):
        """emulate a PUT for browser users with simple form POST"""
        # return same result page as for GET app/tags/data_id for convenience

        def putBody():
            self.insertForStore()
            return None

        def putPostCommit(results):
            inf = web.ctx.env['wsgi.input']

            if self.url == None:
                boundary1, boundaryN = self.scanFormHeader(inf)
                f = self.storeInput(inf)

                # now we have to remove the trailing part boundary we
                # copied to disk by being lazy above...
                # SEEK_END attribute not supported by Python 2.4
                # f.seek(0 - len(boundaryN), os.SEEK_END)
                f.seek(0 - len(boundaryN), 2)
                f.truncate() # truncate to current seek location
                # bytes = f.tell()
                f.close()

            raise web.seeother('/tags/%s' % (urlquote(self.data_id)))

        def deleteBody():
            if self.vers_id == None:
                raise NotFound()
            results = self.select_file_version()
            if len(results) == 0:
                raise NotFound()
            self.delete_file_version()
            return (results[0], self.select_file_versions())

        def deletePostCommit(results):
            file_version, versions = results
            if file_version.url == None:
                filename = self.makeFilename()
                os.unlink(filename)
            if len(versions) > 0:
                raise web.seeother('/history/%s' % (self.data_id))
            else:
                raise web.seeother('/file')

        contentType = web.ctx.env['CONTENT_TYPE'].lower()
        if contentType[0:19] == 'multipart/form-data':
            # we only support file PUT simulation this way
            return self.dbtransact(putBody, putPostCommit)

        elif contentType[0:33] == 'application/x-www-form-urlencoded':
            storage = web.input()
            self.action = storage.action
            try:
                self.url = storage.url
            except:
                self.url = None

            if self.action == 'delete':
                return self.dbtransact(deleteBody, deletePostCommit)
            elif self.action == 'put':
                return self.dbtransact(putBody, putPostCommit)
            else:
                raise web.BadRequest()

        else:
            raise web.BadRequest()
