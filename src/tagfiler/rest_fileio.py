

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
import traceback
import sys

import os
import web
import subprocess
import random
import re
import sys
import time
import datetime
import pytz

from dataserv_app import Application, NotFound, BadRequest, Conflict, RuntimeError, Forbidden, urlquote, urlunquote, parseBoolString, predlist_linearize, path_linearize, jsonWriter, make_temporary_file, yieldBytes
from subjects import Subject

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


def choose_content_type(clientval, guessedval, taggedval, name=None):
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

    if name:
        # try to use client-provided name extensions to clean up poor guessing by CentOS 'file' utility
        m = re.match(r'.+\.(?P<ext>[^.]+)', name)
        if m:
            ext = m.groupdict()['ext']
        
            if bguessedval in [ 'application/x-zip', 'application/zip' ] and name:
                guessedval = {
                    'xlsx' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'docx' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'pptx' : 'application/vnd.openxmlformats-officedocument.presentationml.presentation'                    
                    }.get(ext, guessedval)
            elif bguessedval in [ 'application/msword' ]:
                guessedval = {
                    'ppt' : 'application/vnd.ms-powerpoint',
                    'xls' : 'application/vnd.ms-excel'
                    }.get(ext, guessedval)
            elif bguessedval in [ 'text/plain' ]:
                guessedval = {
                    'csv' : 'text/csv'
                    }.get(ext, guessedval)

            bguessedval = basetype(guessedval)

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

class FileIO (Subject):
    """Basic bulk file I/O, extending subject CRUD

    These handler functions attempt to do buffered I/O to handle
    arbitrarily large file sizes without requiring arbitrarily large
    memory allocations.

    """
    __slots__ = [ 'formHeaders', 'action', 'filetype', 'bytes', 'client_content_type', 'referer' ]

    def __init__(self, parser=None, appname=None, catalog_id=None, path=None, queryopts=None):
        Subject.__init__(self, parser, appname, catalog_id, path, queryopts)
        self.api = 'file'
        self.action = None
        self.key = None
        self.bytes = None
        self.referer = None
        self.update = False
        self.subject = None
        self.newMatch = None
        self.mergeSubjpredsTags = False

    def GET(self, uri, sendBody=True):
        global mime_types_suffixes

        def body():
            Subject.get_body(self)
            txids = [ self.path_txid ]
            # read authz implied by finding subject
            if self.subject.dtype == 'file':
                filename = self.config['store path'] + '/' + self.subject.file
                f = None
                # use the file as raw bytes
                self.set_http_etag(max(txids))
                if self.http_is_cached():
                    # skip the file handling
                    return None, None, True
                f = open(filename, "rb", 0)
                if self.subject.get('content-type', None) == None:
                    p = subprocess.Popen(['/usr/bin/file', '-i', '-b', filename], stdout=subprocess.PIPE)
                    line = p.stdout.readline()
                    self.subject['content-type'] = line.strip().split(' ', 1)[0]
                return f, False
            else:
                raise Conflict(self, data='The resource "%s" does not support file IO.' % path_linearize(self.path))

        def postCommit(results):
            f, cached = results
            if cached:
                web.ctx.status = '304 Not Modified'
                self.emit_headers()
                return results
            else:
                return results

        f, cached = self.dbtransact(body, postCommit)

        if cached:
            # short out here
            return

        # we only get here if we were able to both:
        #   a. open the file for reading its content
        #   b. obtain its content-type from /usr/bin/file test

        # fix up some ugliness in CentOS 'file -i -b' outputs
        content_type = re.sub('application/x-zip', 'application/zip', self.subject['content-type'])

        if self.subject.name:
            mime_type = content_type.split(';')[0]
            m = re.match(r'^.+\.[^.]{1,4}', self.subject.name)
            if m:
                disposition_name = self.subject.name
            else:
                try:
                    suffix = mime_types_suffixes[mime_type]
                    disposition_name = self.subject.name + '.' + suffix
                except:
                    disposition_name = self.subject.name
        else:
            disposition_name = self.dataname
        
        # SEEK_END attribute not supported by Python 2.4
        # f.seek(0, os.SEEK_END)
        f.seek(0, 2)
        length = f.tell()
        # SEEK_SET is not supported by Python 2.4
        # f.seek(0, os.SEEK_SET)
        f.seek(0, 0)

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

            if rangeset != None:

                if len(rangeset) == 0:
                    # range not satisfiable
                    web.ctx.status = '416 Requested Range Not Satisfiable'
                    self.header("Content-Range", "bytes */%s" % length)
                    self.emit_headers()
                    return
                elif len(rangeset) == 1:
                    # result is a single Content-Range body
                    first, last = rangeset[0]
                    web.ctx.status = '206 Partial Content'
                    self.header('Content-Length', last - first + 1)
                    self.header('Content-Range', "bytes %s-%s/%s" % (first, last, length))
                    self.content_range = ( last - first, length )
                    self.header('Content-Type', content_type)
                    self.header('Content-Disposition', 'attachment; filename="%s"' % (disposition_name))
                    self.emit_headers()
                    for res in yieldBytes(f, first, last, self.config['chunk bytes']):
                        self.midDispatch()
                        yield res
                else:
                    # result is a multipart/byteranges ?
                    boundary = "%s%s%s" % (random.randrange(0, 0xFFFFFFFFL),
                                           random.randrange(0, 0xFFFFFFFFL),
                                           random.randrange(0, 0xFFFFFFFFL))
                    self.header('Content-Type', 'multipart/byteranges; boundary=%s' % boundary)
                    self.emit_headers()

                    xmit_length = 0
                    for r in range(0,len(rangeset)):
                        first, last = rangeset[r]
                        xmit_length += last - first
                        yield '\r\n--%s\r\nContent-type: %s\r\nContent-range: bytes %s-%s/%s\r\nContent-Disposition: attachment; filename="%s"\r\n\r\n' \
                              % (boundary, content_type, first, last, length, disposition_name)
                        for res in yieldBytes(f, first, last, self.config['chunk bytes']):
                            self.midDispatch()
                            yield res
                        if r == len(rangeset) - 1:
                            yield '\r\n--%s--\r\n' % boundary

                    self.content_range = ( xmit_length, length )
            else:
                # result is whole body
                web.ctx.status = '200 OK'
                self.emit_headers()
                self.header('Content-type', content_type)
                self.header('Content-Length', length)
                self.content_range = ( length, length )
                self.header('Content-Disposition', 'attachment; filename="%s"' % (disposition_name))
                
                for buf in yieldBytes(f, 0, length - 1, self.config['chunk bytes']):
                    self.midDispatch()
                    yield buf

        else: # not sendBody...
            # we only send headers (for HTTP HEAD)
            self.emit_headers()
            self.header('Content-type', content_type)
            self.header('Content-Length', length)
            self.content_range = ( 0, length )
            pass

        f.close()

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

    def insertForStore_contentType(self, newfile):
        """For file bodies, try guessing content-type to refine choice..."""
        tagged_content_type = Subject.insertForStore_contentType(self, newfile)
        if newfile.bytes != None:
            try:
                filename = self.config['store path'] + '/' + newfile.file
                p = subprocess.Popen(['/usr/bin/file', '-i', '-b', filename], stdout=subprocess.PIPE)
                line = p.stdout.readline()
                guessed_content_type = line.strip()
            except:
                guessed_content_type = None

            content_type = choose_content_type(self.client_content_type,
                                               guessed_content_type,
                                               tagged_content_type,
                                               name=newfile.name)
            return content_type
        else:
            return tagged_content_type

    def storeInput(self, inf, f, flen=None, cfirst=None, clen=None):
        """copy content stream"""

        if cfirst != None:
            f.seek(cfirst, 0)

        bytes = 0
        eof = False
        while not eof:
            if clen != None:
                buf = inf.read(min((clen - bytes), self.config['chunk bytes']))
            else:
                buf = inf.read(self.config['chunk bytes'])

            f.write(buf)
            buflen = len(buf)
            bytes = bytes + buflen
            self.midDispatch()

            if clen != None:
                if clen == bytes:
                    eof = True
                elif buflen == 0:
                    f.close()
                    raise BadRequest(self, data="Only received %s bytes out of expected %s bytes." % (bytes, clen)) # entity undersized
            elif buflen == 0:
                eof = True

        if flen != None:
            f.seek(flen,0)
            f.truncate()
        else:
            f.seek(0,2)
            flen = f.tell()

        self.content_range = ( bytes, flen )

        #web.debug('stored %d of %d bytes' %( bytes, flen))
        return (bytes, flen)

    def getTemporary(self, mode):
        """get a temporary file"""

        # make a psuedo-randomly balanced tree to optimize directory lookups for large catalogs
        # cannot use subject.id because we don't know it until postwrite phase
        
        userparts = path_linearize(self.path, lambda x : urlquote(x, safe="/"))
        userparts = [ part for part in userparts.split('/') if part ]

        if len(userparts) == 0:
            # anonymous node, so name it with timestamp for decent hash distribution
            userparts = [ 'anonymous-node-%s' % datetime.datetime.now(pytz.timezone('UTC')) ]
        
        hashval = '%8.8x' % ( abs(hash(userparts[0])) % (pow(2,31) - 1 ) )
        dir = self.config['store path'] + '/%s/%s/%s' % ( hashval[0:2], hashval[2:5], hashval[5:] )

        # include leading user parts in dir path
        for part in userparts[0:-1]:
            dir += '/%s' % part

        # use final user part as base of random filename
        prefix = '%s-' % userparts[-1]

        return make_temporary_file(prefix, dir, mode)

    def put_preWriteBody_result(self):
        """Extension for returning writable file for byte I/O..."""
        if self.update:
            if self.unique:
                if self.subject.dtype == 'file' and self.subject.file:
                    filename = self.config['store path'] + '/' + self.subject.file
                    f = open(filename, 'r+b', 0)
                    return f
                else:
                    raise Conflict(self, data='The resource "%s" does not support byte-range update.' % path_linearize(self.path))
            else:
                raise Conflict(self, data='The resource "%s" is not unique, so byte-range update is unsafe.' % path_linearize(self.path))
        
    def PUT(self, uri, post_method=False):
        """store file content from client"""
        self.uri = uri
        cfirst, clast, clen, flen, self.partial_content = self.put_prepareRequest()

        inf = web.ctx.env['wsgi.input']
        f = self.dbtransact(lambda : self.put_preWriteBody(post_method=post_method),
                            lambda result : result)

        self.subject_prewrite = self.subject
        self.mustInsert = False

        # we get here if write is not disallowed
        if f == None:
            # create a new disk file for 
            f, filename = self.getTemporary('wb')
            self.file = filename[len(self.config['store path'])+1:]
            self.dtype = 'file'
            self.mustInsert = True
            self.update = False
        else:
            filename = None

        # we only get here if we have a file to write into
        wbytes, flen = self.storeInput(inf, f, flen, cfirst, clen)
        f.close()

        self.bytes = flen
        self.wbytes = wbytes

        now = datetime.datetime.now(pytz.timezone('UTC'))
        if not self.mustInsert \
                and self.subject.dtype == 'file' \
                and self.unique \
                and self.context.client == self.subject['modified by'] \
                and self.subject['modified'] and (now - self.subject['modified']).seconds < 5 \
                and self.subject['bytes'] == self.bytes \
                and len(self.queryopts.keys()) == 0:
            # skip tag update transaction if and only if it is a noop
            return self.put_postWritePostCommit([])
        else:
            try:
                result = self.dbtransact(lambda : self.put_postWriteBody(post_method=post_method),
                                         lambda result : self.put_postWritePostCommit(result))
                return result
            except web.SeeOther:
                raise
            except:
                if filename:
                    self.deleteFile(filename)
                raise

    def POST(self, uri):
        """emulate a PUT for browser users with simple form POST"""
        # return same result page as for GET app/tags/subjpreds for convenience

        def preWritePostCommit(results):
            f = results
            if f != None:
                raise BadRequest(self, data='Cannot update an existing file via POST.')
            return None
        
        def putPostCommit(junk_files):
            self.emit_headers()
            if junk_files:
                self.deletePrevious(junk_files)
            view = ''
            try:
                view = '?view=%s' % urlquote('%s' % self.subject['default view'])
            except:
                pass
            if view == '' and self.subject.dtype:
                view = '?view=%s' % urlquote('%s' % self.subject.dtype)
            acceptType = self.preferredType()
            url = self.config.homepath + '/' + self.api + '/' + self.subject2identifiers(self.subject)[0]
            self.header('Location', url)
            if acceptType == 'application/json':
                self.header('Content-Type', 'application/json')
                return jsonWriter(self.subject)
            else:
                #self.header('Content-Type', 'text/uri-list')
                #web.ctx.status = '204 No Content'
                return '%s\n' % url

        contentType = web.ctx.env.get('CONTENT_TYPE', "").lower()
        if contentType[0:19] == 'multipart/form-data':
            # we only support file PUT simulation this way
            post_method = True
            if self.queryopts.has_key('name'):
                self.name = self.queryopts['name']
            else:
                post_method = False
                
            # do pre-test of permissions to abort early if possible
            self.dbtransact(lambda : self.put_preWriteBody(post_method=post_method),
                            preWritePostCommit)

            inf = web.ctx.env['wsgi.input']
            boundary1, boundaryN = self.scanFormHeader(inf)
            f, tempFileName = self.getTemporary("w+b")

            try:
                self.client_content_type = self.formHeaders['content-type']
            except:
                self.client_content_type = None

            try:
                try:
                    #self.db._db_cursor().connection.close()
                    pass
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
                    raise BadRequest(self, data="The multipart/form-data terminal boundary was not found.")
                self.file = tempFileName[len(self.config['store path'])+1:len(tempFileName)]
                self.dtype = 'file'
                self.bytes = bytes

                result = self.dbtransact(lambda : self.insertForStore(allow_blank=True, post_method=post_method),
                                         putPostCommit)
                return result
            except web.SeeOther:
                raise
            except:
                self.deleteFile(tempFileName)
                raise

        elif contentType[0:33] == 'application/x-www-form-urlencoded':
            return Subject.POST(self, uri)

        else:
            return self.PUT(uri, post_method=True)


