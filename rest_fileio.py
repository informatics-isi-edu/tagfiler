

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
import tempfile
import random
import re
import traceback
import sys
import time
import datetime
import pytz
import urllib

from dataserv_app import Application, NotFound, BadRequest, Conflict, RuntimeError, Forbidden, urlquote, parseBoolString, predlist_linearize, reduce_name_pred

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
        rlen = len(buf)
        byte += rlen
        yield buf
        if rlen < readbytes:
            # undersized read means file got shorter (possible w/ concurrent truncates)
            web.debug('tagfiler.rest_fileio.yieldBytes: short read to %d instead of %d bytes!' % (byte, last))
            # compensate as if the file has a hole, since it is too late to signal an error now
            byte = rlen
            yield bytearray(readbytes - rlen)
            

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

file_cache = dict()  # cache[(user, predlist)] = (ctime, fileresult)
file_cache_time = 5 # maximum cache time in seconds

class FileIO (Application):
    """Basic bulk file I/O

    These handler functions attempt to do buffered I/O to handle
    arbitrarily large file sizes without requiring arbitrarily large
    memory allocations.

    """
    __slots__ = [ 'formHeaders', 'action', 'filetype', 'bytes', 'client_content_type', 'referer' ]

    def __init__(self):
        Application.__init__(self)
#        self.skip_preDispatch = True
        self.action = None
        self.filetype = 'file'
        self.key = None
        self.url = None
        self.bytes = None
        self.referer = None
        self.update = False
        self.subject = None
        self.newMatch = None
        #self.needed_db_globals = []  # turn off expensive db queries we ignore
        self.cachekey = None

    def populate_subject(self, enforce_read_authz=True, allow_blank=False):
        self.unique = self.validate_predlist_unique(acceptName=True, acceptBlank=allow_blank)

        if self.unique == None:
            # this happens only with allow_blank=True when there is no uniqueness and no name
            raise NotFound('dataset matching non-unique predicate list')
        elif self.unique:
            # this means we have an exact match which may not be the latest version
            self.versions = 'any'
        elif self.unique == False:
            # this happens when we accept a name w/o version in lieu of unique predicate(s)
            self.versions = 'latest'
        # 'read' authz is implicit in this query
        results = self.select_files_by_predlist(predlist=self.predlist,
                                                listtags=['content-type', 'bytes', 'url',
                                                          'modified', 'modified by', 'name', 'version', 'Image Set',
                                                          'tagdef', 'typedef', 'config', 'view'],
                                                versions=self.versions,
                                                enforce_read_authz=enforce_read_authz)
        if len(results) == 0:
            raise NotFound('dataset matching "%s"' % predlist_linearize(self.predlist))
        self.subject = results[0]
       
        # get file tag which is 'system' authz model so not included already
        results = self.select_tag_noauthn(self.subject, self.globals['tagdefsdict']['file'])
        if len(results) > 0:
            self.subject.file = results[0].value
        else:
            self.subject.file = None

        self.datapred, self.dataid, self.dataname, self.subject.dtype = self.subject2identifiers(self.subject)

    def GET(self, uri, sendBody=True):
        global mime_types_suffixes

        def body():
            self.populate_subject()
            # read authz implied by finding subject
            self.newMatch = True
            return (self.subject, self.subject['content-type'])

        def postCommit(result):
            # if the dataset is a remote URL, just redirect client
            result, content_type = result
            if result.dtype == 'url':
                opts = [ '%s=%s' % (opt[0], urlquote(opt[1])) for opt in self.queryopts.iteritems() ]
                if len(opts) > 0:
                    querystr = '&'.join(opts)
                    if len(result.url.split("?")) > 1:
                        querystr = '&' + querystr
                    else:
                        querystr = '?' + querystr
                else:
                    querystr = ''
                raise web.seeother(result.url + querystr)
            elif result.dtype == 'file':
                filename = self.config['store path'] + '/' + self.subject.file
                try:
                    f = open(filename, "rb", 0)
                    if content_type == None:
                        p = subprocess.Popen(['/usr/bin/file', '-i', '-b', filename], stdout=subprocess.PIPE)
                        line = p.stdout.readline()
                        content_type = line.strip()
                    return (f, content_type)
                except:
                    # this may happen sporadically under race condition:
                    # query found unique file, but someone replaced it before we opened it
                    return (None, None)
            else:
                datapred, dataid, dataname, dtype = self.subject2identifiers(result)
                raise web.seeother('%s/tags/%s' % (self.globals['home'], datapred))

        now = datetime.datetime.now(pytz.timezone('UTC'))
        def preRead():
            f = None
            content_type = None
            self.subject = None
            cachekey = (self.authn.role, predlist_linearize(self.predlist))
            cached = file_cache.get((self.authn.role, cachekey), None)
            if cached:
                ctime, subject = cached
                if (now - ctime).seconds < file_cache_time:
                    self.subject = subject
                    f, content_type = postCommit((subject, subject['content-type']))
                    if not f:
                        file_cache.pop((self.authn.role, cachekey), None)
                else:
                    file_cache.pop((self.authn.role, cachekey), None)
            if not f:
                return self.dbtransact(body, postCommit)
            else:
                # never re-cache a cache hit
                self.newMatch = False
                return (f, content_type)

        count = 0
        limit = 10
        f = None
        while not f:
            count = count + 1
            if count > limit:
                # we failed after too many tries, just give up
                # if this happens in practice, need to investigate or redesign...
                raise web.internallerror('Could not access local copy of ' + predlist_linearize(self.predlist))

            # we do this in a loop to compensate for race conditions noted above
            f, content_type = preRead()

        if self.newMatch:
            cachekey = (self.authn.role, predlist_linearize(self.predlist))
            file_cache[(self.authn.role, cachekey)] = (now, self.subject)

        # we only get here if we were able to both:
        #   a. open the file for reading its content
        #   b. obtain its content-type from /usr/bin/file test

        # fix up some ugliness in CentOS 'file -i -b' outputs
        content_type = re.sub('application/x-zip', 'application/zip', content_type)

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

        #web.header('Content-Location', self.globals['homepath'] + '/file/%s@%d' % (urlquote(self.subject.name), self.subject.version))
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

            self.log('GET', dataset=predlist_linearize(self.predlist))
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
                    for res in yieldBytes(f, first, last, self.config['chunk bytes']):
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
                        for res in yieldBytes(f, first, last, self.config['chunk bytes']):
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
                
                for buf in yieldBytes(f, 0, length - 1, self.config['chunk bytes']):
                    self.midDispatch()
                    yield buf

        else: # not sendBody...
            # we only send headers (for HTTP HEAD)
            web.header('Content-type', content_type)
            web.header('Content-Length', length)
            pass

        f.close()


    def HEAD(self, uri):
        return self.GET(uri, sendBody=False)

    def delete_body(self):
        self.populate_subject()
        if not self.subject.writeok:
            raise Forbidden('delete of dataset "%s"' % predlist_linearize(self.predlist))
        self.enforce_file_authz_special('write', self.subject)
        self.delete_file(self.subject)
        self.txlog('DELETE', dataset=predlist_linearize(self.predlist))
        return (self.subject)

    def delete_postCommit(self, result, set_status=True):
        if result.dtype == 'file' and result.file != None:
            """delete the file"""
            filename = self.config['store path'] + '/' + result.file
            dir = os.path.dirname(filename)
            self.deleteFile(filename)
            web.ctx.status = '204 No Content'
        return ''

    def DELETE(self, uri):
        def body():
            return self.delete_body()
        def postCommit(result):
            return self.delete_postCommit(result)
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

    def insertForStore(self, allow_blank=False):
        """Only call this after creating a new file on disk!"""
        content_type = None
        junk_files = []

        # don't blindly trust DB data from earlier transactions... do a fresh lookup
        self.mergePredlistTags = False
        status = web.ctx.status
        try:
            self.populate_subject(allow_blank=allow_blank)
            if not self.subject.writeok:
                raise Forbidden('write to file "%s"' % predlist_linearize(self.predlist))
            self.enforce_file_authz_special('write', self.subject)
            self.newMatch = True
                
        except NotFound:
            web.ctx.status = status
            self.subject = None
            self.update = False
            # this is a new dataset independent of others
            if len( set(self.config['file write users']).intersection(set(self.authn.roles).union(set('*'))) ) == 0:
                raise Forbidden('creation of datasets')
            # raise exception if predlist invalid for creating objects
            self.unique = self.validate_predlist_unique(acceptName=True, acceptBlank=allow_blank, restrictSchema=True)
            self.mergePredlistTags = True

        if self.unique == False:
            # this is the case where we are using name/version semantics for files
            if self.subject:
                self.version = self.subject.version + 1
                self.name = self.subject.name
            else:
                self.version = 1
                self.name = reduce(reduce_name_pred, self.predlist + [ dict(tag='', op='', vals=[]) ] )
        else:
            self.name = None
            self.version = None

        if self.bytes != None:
            # only deal with content_type guessing when we have byte payload
            if self.subject:
                tagged_content_type = self.subject['content-type']
            else:
                tagged_content_type = None

            try:
                filename = self.config['store path'] + '/' + self.file
                p = subprocess.Popen(['/usr/bin/file', '-i', '-b', filename], stdout=subprocess.PIPE)
                line = p.stdout.readline()
                guessed_content_type = line.strip()
            except:
                guessed_content_type = None

            content_type = choose_content_type(self.client_content_type,
                                               guessed_content_type,
                                               tagged_content_type)

        if self.subject:
            if self.unique == False:
                # this is the case where we create a new version of an existing named file
                self.txlog('UPDATE', dataset=predlist_linearize(self.predlist))
                self.id = self.insert_file(self.name, self.version, self.file)
            elif self.unique:
                # this is the case where we update an existing uniquely tagged file in place
                self.txlog('UPDATE', dataset=predlist_linearize(self.predlist))
                self.id = None
                if self.subject.file:
                    junk_files.append(self.subject.file)
                if self.file:
                    self.set_tag(self.subject, self.globals['tagdefsdict']['file'], self.file)
                elif self.subject.file:
                    self.delete_tag(self.subject, self.globals['tagdefsdict']['file'])
            else:
                # this is the case where we create a new blank node similar to an existing blank node
                self.txlog('CREATE', dataset=predlist_linearize(self.predlist))
                self.id = self.insert_file(self.name, self.version, self.file)
        else:
            # anybody is free to insert new uniquely named file
            self.txlog('CREATE', dataset=predlist_linearize(self.predlist))
            self.id = self.insert_file(self.name, self.version, self.file)

        if self.id != None:
            newfile = web.Storage(id=self.id,
                                  dtype=self.dtype,
                                  name=self.name,
                                  version=self.version,
                                  bytes=self.bytes,
                                  file=self.file,
                                  owner=self.authn.role,
                                  writeok=True,
                                  url=self.url)

            newfile['content-type'] = content_type
        else:
            # we are updating an existing (unique) object rather than inserting a new one
            newfile = self.subject
        
        self.updateFileTags(newfile, self.subject)

        self.subject = newfile
        return junk_files

    def updateFileTags(self, newfile, basefile):
        if not basefile:
            # set initial tags on all new, independent objects
            self.set_tag(newfile, self.globals['tagdefsdict']['owner'], newfile.owner)
            self.set_tag(newfile, self.globals['tagdefsdict']['created'], 'now')
            if newfile.version:
                self.set_tag(newfile, self.globals['tagdefsdict']['version created'], 'now')
            if newfile.name and newfile.version:
                self.set_tag(newfile, self.globals['tagdefsdict']['vname'], '%s@%s' % (newfile.name, newfile.version))
        elif newfile.id != basefile.id and newfile.version and basefile.version:
            # create derived versioned file from existing versioned file
            self.set_tag(newfile, self.globals['tagdefsdict']['version created'], 'now')
            self.set_tag(newfile, self.globals['tagdefsdict']['vname'], '%s@%s' % (newfile.name, newfile.version))

            for result in self.select_filetags_noauthn(basefile):
                if result.tagname not in [ 'bytes', 'content-type', 'key', 
                                           'latest with name', 'modified', 'modified by', 'name', 'sha256sum',
                                           'url', 'file', 'version created', 'version', 'vname' ]:
                    tags = self.select_tag_noauthn(basefile, self.globals['tagdefsdict'][result.tagname])
                    for tag in tags:
                        if hasattr(tag, 'value'):
                            self.set_tag(newfile, self.globals['tagdefsdict'][result.tagname], tag.value)
                        else:
                            self.set_tag(newfile, self.globals['tagdefsdict'][result.tagname])

        if not basefile or self.authn.role != basefile['modified by'] or basefile.id != newfile.id:
            self.set_tag(newfile, self.globals['tagdefsdict']['modified by'], self.authn.role)

        now = datetime.datetime.now(pytz.timezone('UTC'))
        if not basefile or not basefile['modified'] or (now - basefile.modified).seconds > 5 or basefile.id != newfile.id:
            self.set_tag(newfile, self.globals['tagdefsdict']['modified'], 'now')

        if newfile.dtype == 'file':
            if not basefile or newfile.bytes != basefile.bytes or basefile.id != newfile.id:
                self.set_tag(newfile, self.globals['tagdefsdict']['bytes'], newfile.bytes)
            if not basefile or basefile.url and basefile.version == newfile.version:
                self.delete_tag(newfile, self.globals['tagdefsdict']['url'])
                
            if newfile['content-type'] and (not basefile or basefile['content-type'] != newfile['content-type'] or basefile.id != newfile.id):
                self.set_tag(newfile, self.globals['tagdefsdict']['content-type'], newfile['content-type'])
        elif newfile.dtype in [ None, 'url' ]:
            if basefile and basefile.bytes != None and basefile.id == newfile.id:
                self.delete_tag(newfile, self.globals['tagdefsdict']['bytes'])
            if basefile and basefile['content-type'] != None and basefile.id == newfile.id:
                self.delete_tag(newfile, self.globals['tagdefsdict']['content-type'])
            if newfile.url:
                self.set_tag(newfile, self.globals['tagdefsdict']['url'], newfile.url)
            if self.key:
                self.set_tag(newfile, self.globals['tagdefsdict']['key'], self.key)

        # try to apply tags provided by user as PUT/POST queryopts in URL
        #    and tags constrained in predlist (only if creating new independent object)
        # they all must work to complete transaction
        tagvals = [ (k, [v]) for k, v in self.queryopts.items() ]

        if self.mergePredlistTags:
            tagvals = tagvals + [ (pred['tag'], pred['vals']) for pred in self.predlist if pred['tag'] not in [ 'name', 'version' ] ]

        for tagname, values in tagvals:
            tagdef = self.globals['tagdefsdict'].get(tagname, None)
            if tagdef == None:
                raise NotFound('tagdef="%s"' % tagname)
            self.enforce_tag_authz('write', newfile, tagdef)
            if tagdef.typestr == 'empty':
                self.set_tag(newfile, tagdef)
            else:
                for value in values:
                    self.set_tag(newfile, tagdef, value)
            self.txlog('SET', dataset=self.subject2identifiers(newfile)[0], tag=tagname, value=values)

        if not basefile:
            # only remap on newly created files
            srcroles = set(self.config['policy remappings'].keys()).intersection(self.authn.roles)
            if len(srcroles) == 1:
                try:
                    t = self.db.transaction()
                    srcrole = srcroles.pop()
                    dstrole, readusers, writeusers = self.config['policy remappings'][srcrole]
                    #web.debug(self.remap)
                    #web.debug('remap:', self.remap[srcrole])
                    for readuser in readusers:
                        self.set_tag(newfile, self.globals['tagdefsdict']['read users'], readuser)
                        self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='read users', value=readuser)
                    for writeuser in writeusers:
                        self.set_tag(newfile, self.globals['tagdefsdict']['write users'], writeuser)
                        self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='write users', value=writeuser)
                    if dstrole:
                        self.set_tag(newfile, self.globals['tagdefsdict']['owner'], dstrole)
                    self.txlog('REMAP', dataset=self.subject2identifiers(newfile)[0], tag='owner', value=dstrole)
                    t.commit()
                except:
                    et, ev, tb = sys.exc_info()
                    web.debug('got exception "%s" during owner remap attempt' % str(ev),
                              traceback.format_exception(et, ev, tb))
                    t.rollback()
                    raise
            elif len(srcroles) > 1:
                raise Conflict("Ambiguous remap rules encountered.")

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
            
        dir = self.config['store path'] + '/' + predlist_linearize(self.predlist)

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
                f = open(filename, mode, 0)
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
            self.deleteFile(self.config['store path'] + '/' + file)

    def putPreWriteBody(self):
        status = web.ctx.status
        try:
            self.populate_subject(enforce_read_authz=False)
            if not self.subject.readok:
                raise Forbidden('access to file "%s"' % predlist_linearize(self.predlist))
            if not self.subject.writeok:
                raise Forbidden('write to file "%s"' % self.subject2identifiers(self.subject)[0])
            self.enforce_file_authz_special('write', self.subject)
            if self.update:
                if self.unique:
                    if self.subject.dtype == 'file' and self.subject.file:
                        # we can cache this validated result
                        self.newMatch = True
                        filename = self.config['store path'] + '/' + self.subject.file
                        f = open(filename, 'r+b', 0)
                        return f
                    else:
                        raise Conflict(data='The resource "%s" does not support byte-range update.' % predlist_linearize(self.predlist))
                else:
                    raise Conflict(data='The resource "%s" is not unique, so byte-range update is unsafe.' % predlist_linearize(self.predlist))
                
        except NotFound:
            web.ctx.status = status
            self.subject = None
            if self.unique:
                # not found w/ unique predlist is not to be confused with creating new files
                raise
            # not found and not unique, treat as new file put
            if len( set(self.config['file write users']).intersection(set(self.authn.roles).union(set('*'))) ) == 0:
                raise Forbidden('creation of datasets')
            # raise exception if predlist invalid for creating objects
            self.unique = self.validate_predlist_unique(acceptName=True, acceptBlank=True, restrictSchema=True)
            self.mergePredlistTags = True

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
                    raise BadRequest(data='Range: %s does not match content-length %s.' % (content_range, clen))
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
        else:
            self.update = False

        now = datetime.datetime.now(pytz.timezone('UTC'))
        def preWriteCached():
            f = None
            cachekey = (self.authn.role, predlist_linearize(self.predlist))
            cached = file_cache.get((self.authn.role, cachekey), None)
            if cached:
                ctime, subject = cached
                if subject and (now - ctime).seconds < file_cache_time:
                    self.subject = subject
                    filename = self.config['store path'] + '/' + self.subject.file
                    f = open(filename, 'r+b', 0)
                    if not f:
                        file_cache.pop((self.authn.role, cachekey), None)
                else:
                    file_cache.pop((self.authn.role, cachekey), None)
                    
            if not f:
                return self.dbtransact(preWriteBody, preWritePostCommit)
            else:
                self.newMatch = False
                return f
            
        # this retries if a file was found but could not be opened due to races
        if self.update and len(self.queryopts) == 0:
            f = preWriteCached()
        else:
            # don't trust cache for version updates nor queryopts-based tag writing...
            f = self.dbtransact(preWriteBody, preWritePostCommit)

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

        def postWriteBody():
            # this may repeat in case of database races
            if self.mustInsert:
                try:
                    self.client_content_type = web.ctx.env['CONTENT_TYPE'].lower()
                except:
                    self.client_content_type = None
                return self.insertForStore()
            else:
                # simplified path for chunk updates
                self.subject = self.subject_prewrite
                newfile = web.Storage(self.subject)
                newfile.bytes = self.bytes
                self.updateFileTags(newfile, self.subject)
                return []

        def postWritePostCommit(junk_files):
            if not content_range and junk_files:
                self.deletePrevious(junk_files)
            uri = self.config['home'] + self.config['store path'] + '/' + self.subject2identifiers(self.subject)[0]
            web.header('Location', uri)
            if filename:
                web.ctx.status = '201 Created'
                res = uri
            else:
                web.ctx.status = '204 No Content'
                res = ''
            return res

        if self.newMatch:
            # cache newly obtained results
            cachekey = (self.authn.role, predlist_linearize(self.predlist))
            file_cache[cachekey] = (now, self.subject)
        if not self.mustInsert \
                and self.subject.dtype == 'file' \
                and self.unique \
                and self.authn.role == self.subject['modified by'] \
                and self.subject['modified'] and (now - self.subject['modified']).seconds < 5 \
                and self.subject['bytes'] == self.bytes \
                and not self.subject['url'] \
                and len(self.queryopts.keys()) == 0:
            # skip tag update transaction if and only if it is a noop
            return postWritePostCommit([])
        else:
            try:
                result = self.dbtransact(postWriteBody, postWritePostCommit)
                return result
            except web.SeeOther:
                raise
            except:
                if filename:
                    self.deleteFile(filename)
                raise

    def POST(self, uri):
        """emulate a PUT for browser users with simple form POST"""
        # return same result page as for GET app/tags/predlist for convenience

        def keyBody():
            return self.select_next_key_number()

        def keyPostCommit(results):
            return results

        def preWriteBody():
            return self.putPreWriteBody()

        def preWritePostCommit(results):
            f = results
            if f != None:
                raise BadRequest(data='Cannot update an existing file version via POST.')
            return None
        
        def putBody():
            # we can accept a non-unique predlist only for blank nodes
            return self.insertForStore(allow_blank=(self.dtype==None and self.action=='post'))

        def putPostCommit(junk_files):
            if junk_files:
                self.deletePrevious(junk_files)
            view = '?view=%s' % urlquote('%s' % self.dtype)
            raise web.seeother('/tags/%s%s' % (self.subject2identifiers(self.subject)[0], view))

        def deleteBody():
            return self.delete_body()

        def deletePostCommit(result):
            self.delete_postCommit(result, set_status=False)
            raise web.seeother(self.referer)

        def preDeleteBody():
            self.populate_subject()
            if not self.subject.writeok:
                raise Forbidden('delete of dataset "%s"' % predlist_linearize(self.predlist))
            self.enforce_file_authz_special('write', self.subject)
            
            if self.subject.dtype == 'url':
                if self.subject['Image Set']:
                    ftype = 'imgset'
                else:
                    ftype = 'url'
            else:
                ftype = self.subject.dtype
                
            return ftype

        def preDeletePostCommit(ftype):
            self.globals['datapred'] = self.datapred
            self.globals['dataname'] = self.dataname
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
                self.file = tempFileName[len(self.config['store path'])+1:len(tempFileName)]
                self.dtype = 'file'
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
            
            def get_param(param, default=None):
                """get params from any of web.input(), self.queryopts, self.storage"""
                try:
                    value = storage[param]
                except:
                    value = None
                if value == None:
                    value = self.storage.get(param)
                    if value == None:
                        value = self.queryopts.get(param)
                        if value == None:
                            return default
                    else:
                        return urllib.unquote_plus(value)
                return value

            
            self.key = get_param('key')
            self.action = get_param('action')
            if self.action == None:
                raise BadRequest('Form field "action" is required.')

            self.referer = get_param('referer', "/file")

            if self.action == 'delete':
                return self.dbtransact(preDeleteBody, preDeletePostCommit)
            elif self.action == 'CancelDelete':
                raise web.seeother(self.referer)
            elif self.action == 'ConfirmDelete':
                return self.dbtransact(deleteBody, deletePostCommit)
            elif self.action in [ 'put', 'putsq' , 'post' ]:
                # we only support non-file PUT and POST simulation this way
                self.url = get_param('url')
                self.dtype = None
                if self.action in ['put', 'post']:
                    if self.url != None:
                        self.dtype = 'url'
                elif self.action == 'putsq':
                    # add title=name queryopt for stored queries
                    self.url = get_param('url', '/query') + '?title=%s' % get_param('name')
                       
                return self.dbtransact(putBody, putPostCommit)

            else:
                raise BadRequest(data="Form field action=%s not understood." % self.action)

        else:
            raise BadRequest(data="Content-Type %s not expected via this interface."% contentType)


class LogFileIO (FileIO):

    def __init__(self):
        FileIO.__init__(self)
        self.skip_preDispatch = False


    def GET(self, uri, sendBody=True):

        if not self.authn.hasRoles(['admin']):
            raise Forbidden('read access to log file "%s"' % self.name)

        if not self.config['log path']:
            raise Conflict('log_path is not configured on this server.')

        if self.queryopts.get('action', None) == 'view':
            disposition_name = None
        else:
            disposition_name = self.name

        filename = self.config['log path'] + '/' + self.name
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
                for buf in yieldBytes(f, 0, length - 1, self.config['chunk bytes']):
                    self.midDispatch()
                    yield buf
                if not disposition_name:
                    yield bottom

            f.close()
        
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception in logfileIO',
                      traceback.format_exception(et, ev, tb))
            raise NotFound('log file "%s"' % self.name)
