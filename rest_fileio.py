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
            results = self.select_file()
            if len(results) == 0:
                raise NotFound()
            self.enforceFileRestriction()
            return results[0]

        def postCommit(result):
            # if the dataset is a remote URL, just redirect client
            if result.url:
                raise web.seeother(result.url)

        # we only get here if the dataset is a locally stored file

        self.dbtransact(body, postCommit)
        web.debug('after GETfile dbtransact')

        # need to yield outside postCommit as a generator func
        filename = self.makeFilename()
        f = open(filename, "rb")

        p = subprocess.Popen(['/usr/bin/file', filename], stdout=subprocess.PIPE)
        line = p.stdout.readline()
        # kill attribute is not supported by Python 2.4
        # p.kill()
        web.header('Content-type', line.split(':')[1].strip())
        
        #web.header('Content-type','text/html')
        #web.header('Transfer-Encoding','chunked')

        # SEEK_END attribute not supported by Python 2.4
        # f.seek(0, os.SEEK_END)
        f.seek(0, 2)
        length = f.tell()
        # SEEK_SET is not supported by Python 2.4
        # f.seek(0, os.SEEK_SET)
        f.seek(0, 0)

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
            results = self.select_file()
            if len(results) == 0:
                raise NotFound()
            self.enforceFileRestriction()
            self.delete_file()
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
        results = [ res for res in self.select_file() ]

        if len(results) > 0:
            self.enforceFileRestriction()
            self.delete_file()

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
        return results

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
            return self.insertForStore()

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
            return self.insertForStore()

        def putPostCommit(results):
            inf = web.ctx.env['wsgi.input']

            if self.url == None:
                # then we are posting a file body
                boundary1, boundaryN = self.scanFormHeader(inf)
                f = self.storeInput(inf)

                # now we have to remove the trailing part boundary we
                # copied to disk by being lazy above...
                # SEEK_END attribute not supported by Python 2.4
                # f.seek(0 - len(boundaryN), os.SEEK_END)
                f.seek(0 - len(boundaryN), 2)
                f.truncate() # truncate to current seek location
                bytes = f.tell()
                f.close()

            elif len(results) > 0 and results[0].url == None:
                # we are registering a url on top of a local file
                # try to reclaim space now
                filename = self.makeFilename()
                try:
                    os.unlink(filename)
                except:
                    pass

            raise web.seeother('/tags/%s' % (urlquote(self.data_id)))

        def deleteBody():
            results = self.select_file()
            if len(results) == 0:
                raise NotFound()
            self.enforceFileRestriction()
            self.delete_file()
            return results[0]

        def deletePostCommit(result):
            if result.url == None:
                filename = self.makeFilename()
                os.unlink(filename)
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
