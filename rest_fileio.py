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
    __slots__ = [ 'formHeaders' ]

    def __init__(self):
        Application.__init__(self)

    def makeFilename(self):
        return ''

    def GET(self, uri):

        def body():
            if self.vers_id == None:
                self.vers_id = self.select_file_version_max()
            if self.vers_id == None:
                raise NotFound()
            else:
                results = self.select_file_version()
                if len(results) == 0:
                    raise NotFound()

        def postCommit(results):
            pass

        self.dbtransact(body, postCommit)

        # need to yield outside postCommit as a generator func
        filename = self.makeFilename()
        web.debug(filename)
        f = open(filename, "rb")

        p = subprocess.Popen(['/usr/bin/file', filename], stdout=subprocess.PIPE)
        line = p.stdout.readline()
        p.kill()
        web.header('Content-type', line.split(':')[1].strip())
        
        #web.header('Content-type','text/html')
        #web.header('Transfer-Encoding','chunked')

        f.seek(0, os.SEEK_END)
        length = f.tell()
        f.seek(0, os.SEEK_SET)

        # report length so browsers can show progress bar
        web.header('Content-Length', length)

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

    def DELETE(self, uri):

        def body():
            if self.vers_id == None:
                raise NotFound()
            else:
                results = self.select_file_version()
                if len(results) == 0:
                    raise NotFound()
            self.delete_file_version()

        def postCommit(results):
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

        def body():
            self.insertForStore()
            tagdefs = [ tagdef for tagdef in self.select_tagdefs() ]
            tags = [ result.tagname for result in self.select_file_tags() ]
            tagvals = [ (tag, self.tagval(tag)) for tag in tags ]
            return (tagvals, tagdefs)

        def postCommit(results):
            tagvals, tagdefs = results
            inf = web.ctx.env['wsgi.input']

            boundary1, boundaryN = self.scanFormHeader(inf)
            f = self.storeInput(inf)

            # now we have to remove the trailing part boundary we
            # copied to disk by being lazy above...
            f.seek(0 - len(boundaryN), os.SEEK_END)
            f.truncate() # truncate to current seek location
            #bytes = f.tell()
            f.close()
            target = self.home + web.ctx.homepath + '/tags/' + urlquote(self.data_id)
            if len(tagvals) > 0:
                return self.renderlist("\"%s\" tags" % (self.data_id),
                                       [self.render.FileTagExisting(target, tagvals),
                                        self.render.FileTagNew(target, tagdefs)])
            else:
                return self.renderlist("\"%s\" tags" % (self.data_id),
                                       [self.render.FileTagNew(target, tagdefs)])

        return self.dbtransact(body, postCommit)

