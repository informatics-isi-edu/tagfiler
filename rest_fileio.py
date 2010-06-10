import os
import web
import subprocess
import tempfile

from dataserv_app import Application, NotFound, BadRequest, urlquote

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

    def GETfile(self, uri):

        def body():
            results = self.select_file()
            if len(results) == 0:
                raise NotFound(data='dataset %s' % (self.data_id))
            self.enforceFileRestriction()
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
                    p = subprocess.Popen(['/usr/bin/file', filename], stdout=subprocess.PIPE)
                    line = p.stdout.readline()
                    content_type = line.split(':')[1].strip()
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
        web.header('Content-type', content_type)
        
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
            self.enforceFileRestriction()
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
                    os.rmdir(dir)
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
            self.enforceFileRestriction()
            self.update_file()
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

        # try to apply tags provided by user as PUT/POST queryopts in URL
        # they all must work to complete transaction
        for tagname in self.queryopts.keys():
            self.enforceFileTagRestriction(tagname)
            self.set_file_tag(tagname, self.queryopts[tagname])

        return results

    def storeInput(self, inf, filename, length=None):
        """copy content stream"""

        f = open(filename, "w+b")

        bytes = 0
        eof = False
        while not eof:
            if length:
                buf = inf.read(min((length - bytes), self.chunkbytes))
            else:
                buf = inf.read(self.chunkbytes)

            f.write(buf)
            buflen = len(buf)
            bytes = bytes + buflen

            if length:
                if length == bytes:
                    eof = True
                elif buflen == 0:
                    f.close()
                    os.unlink(filename)
                    raise BadRequest(data="Only received %s bytes out of expected %s bytes." % (bytes, length)) # entity undersized
            elif buflen == 0:
                eof = True

        return (f, bytes)


    def getTemporary(self):
        """get the directory and the prefix for a temporary file"""

        prefix = self.user()
        if prefix != None:
            prefix += '-'
        else:
            prefix = 'anonymous-'
            
        dir = self.store_path + '/' + urlquote(self.data_id)

        if not os.path.exists(dir):
            os.makedirs(dir, mode=0755)

        return (prefix, dir)


    def PUT(self, uri):
        """store file content from client"""

        # this work happens exactly once per web request, consuming input
        inf = web.ctx.env['wsgi.input']
        try:
            length = int(web.ctx.env['CONTENT_LENGTH'])
        except:
            length = None
            # raise LengthRequired()  # if we want to be picky
        user, path = self.getTemporary()
        fileHandle, tempFileName = tempfile.mkstemp(prefix=user, dir=path)
        f, bytes = self.storeInput(inf, tempFileName, length=length)
        f.close()
        self.location = tempFileName[len(self.store_path)+1:len(tempFileName)]
        self.local = True

        def body():
            # this may repeat in case of database races
            self.insertForStore()
            return None

        def postCommit(results):
            return 'Stored %s bytes' % (bytes)

        return self.dbtransact(body, postCommit)


    def POST(self, uri):
        """emulate a PUT for browser users with simple form POST"""
        # return same result page as for GET app/tags/data_id for convenience

        def deletePrevious(result):
            if result.local:
                # previous result had local file, so free it
                filename = self.store_path + '/' + result.location
                dir = os.path.dirname(filename)
                os.unlink(filename)

                """delete the directory if empty"""
                if len(os.listdir(dir)) == 0:
                    os.rmdir(dir)

        def putBody():
            return self.insertForStore()

        def putPostCommit(results):
            if len(results) > 0:
                deletePrevious(results[0])
            raise web.seeother('/tags/%s' % (urlquote(self.data_id)))

        def deleteBody():
            results = self.select_file()
            if len(results) == 0:
                raise NotFound(data='dataset %s' % (self.data_id))
            self.enforceFileRestriction()
            self.delete_file()
            return results[0]

        def deletePostCommit(result):
            deletePrevious(result)
            raise web.seeother('/file')

        contentType = web.ctx.env['CONTENT_TYPE'].lower()
        if contentType[0:19] == 'multipart/form-data':
            # we only support file PUT simulation this way
            inf = web.ctx.env['wsgi.input']
            boundary1, boundaryN = self.scanFormHeader(inf)
            user, path = self.getTemporary()
            fileHandle, tempFileName = tempfile.mkstemp(prefix=user, dir=path)
            f, bytes = self.storeInput(inf, tempFileName)
        
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
