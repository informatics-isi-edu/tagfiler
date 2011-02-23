#!/usr/bin/python

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

import csv
import sys
import pycurl
import os
import traceback
import urllib
from optparse import OptionParser
import StringIO

def urlquote(url):
    """define common URL quote mechanism for registry URL value embeddings"""
    return urllib.quote(url, safe='')

class CSVClient:
    """Class for uploading datasets from CSV files"""
    __slots__ = [ 'csvname', 'user', 'password', 'host', 'authentication', 'csvreader', 'curlclient', 'tags', 'tagdefs', 'tagindex', 'datasetindex', 'fileindex', 'datasets', 'status', 'files' ]
    
    def __init__(self, csvname, user, password, host='psoc.isi.edu', authentication='basic', tagindex=2, fileindex=0, datasetindex=1):
        self.csvname = csvname
        self.user = user
        self.password = password
        self.host = host
        self.authentication = authentication
        self.tagindex = tagindex
        self.datasetindex = datasetindex
        self.fileindex = fileindex
        self.datasets = {}
        self.tags = []
        self.files = []
        self.tagdefs = {}
        self.status = 0
        self.csvreader = self.CSVReader(self.csvname)
        self.curlclient = self.CURLClient(self.user, self.password, self.authentication, self.host)
        
    def upload(self):
        self.readTags()
        if self.status == 0:
            self.readTagdefs()
        if self.status == 0:
            self.readDatasets()
        if self.status == 0:
            self.postDatasets()
        
    def readTags(self):
        """Read the tag names"""
        line = self.csvreader.readline()
        if line:
            for i in range(self.tagindex, len(line)):
                self.tags.append(line[i])
        else:
            print 'Empty file'
            self.status = 1
        
    def readTagdefs(self):
        """Read the tag definitions"""
        for tag in self.tags:
            if self.curlclient.getTagdef(tag) != 0:
                self.status = self.curlclient.status
                continue
            tagdef = self.curlclient.getResponse()
            """Get the tag properties"""
            values = {}
            attributes = tagdef.split('&')
            for attribute in attributes:
                description = attribute.split('=')
                if description[1] != '':
                    values[description[0]] = description[1]
            self.tagdefs[tag] = values
        
    def readDatasets(self):
        """Read and validate the datasets"""
        row = self.csvreader.readline()
        while row:
            row = self.readDataset(row)
        self.validateTagsValues()
        
    def readDataset(self, row):
        """Check file exists"""
        if not os.path.isfile(row[0]) and not os.path.isdir(row[0]):
            print "ERROR: File '%s' does not exist." % row[0]
            self.status = 1
            """Ignore this dataset"""
            while True:
                try:
                    row = self.csvreader.readline()
                    if row[0] and row[0] != '':
                        return row
                except:
                    return None
        else:
            """Get the dataset name"""
            self.files.append(row[0])
            
            if row[self.datasetindex] != '':
                name = row[self.datasetindex]
            else:
                name = os.path.basename(row[0])
                
            if os.path.isfile(row[0]):
                isfile = True
            else:
                isfile = False
                
            dataset = self.Dataset(name, row[0], {})
            """Set the dataset tags"""
            while True:
                for i in range(self.tagindex,len(row)):
                    if row[i]:
                        dataset.add(self.tags[i-self.tagindex], row[i])
                try:
                    row = self.csvreader.readline()
                    if row[0] and row[0] != '':
                        break
                except:
                    row = None
                    break
                
            if isfile:
                self.datasets[name] = dataset
            else:
                self.readDatasetTree(dataset)
                
            return row

    def readDatasetTree(self, dataset):
        """Read a dataset directory"""
        for file in os.listdir(dataset.file):
            subdataset = self.Dataset("%s%s%s" % (dataset.name, os.sep, file), "%s%s%s" % (dataset.file, os.sep, file), dataset.tags)
            if os.path.isfile(subdataset.file):
                self.datasets[subdataset.name] = subdataset
            else:
                self.readDatasetTree(subdataset)
                

    def validateTagsValues(self):
        """Validate tags values"""
        for dataset, datasetdefs in self.datasets.iteritems():
            for tag, tagvalues in datasetdefs.iteritems():
                if len(tagvalues) > 1 and self.tagdefs[tag]['multivalue'] == 'False' and datasetdefs.file in self.files:
                    print "ERROR: Tag '%s\' in dataset '%s' is not allowed to have multiple values." % (tag, dataset)
                    self.status = 1
        
    def postDatasets(self):
        """Post the datasets"""
        for dataset, datasetdefs in self.datasets.iteritems():
            """Upload the dataset file"""
            self.status = self.curlclient.upload(dataset, datasetdefs.file)
                
            if self.status != 0:
                return
                
            """Upload the dataset tags"""
            values = self.tagsToString(datasetdefs)
            if len(values) > 0:
                   self.status = self.curlclient.addTags(dataset, values)
                   
            if self.status != 0:
                print "ERROR: %s, Can not add tags in dataset '%s'" % (self.status, dataset)
                return
        
    def tagsToString(self, datasetdefs):
        values = []
        for tag, tagvalues in datasetdefs.iteritems():
            try:
                self.tagdefs[tag]['typestr']
                """Tag with values"""
                values.extend(["%s=%s" % (urlquote(tag), urlquote(value)) for value in tagvalues])
            except:
                """Tag without values"""
                values.append("%s=" % urlquote(tag))
                
        return "&".join([value for value in values])
        
    def trace(self):
        print self.tags
        print self.tagdefs
        print self.datasets
        
    class CSVReader:
        """Class for reading CSV files"""
        __slots__ = [ 'reader' ] 

        def __init__(self, csvname):
            try:
                self.reader = csv.reader(open(csvname))
            except:
                print "Can not open file '%s'" % csvname
                traceback.print_stack()
                sys.exit()
                
        def readline(self):
            """Get the next non empty line"""
            try:
                while True:
                    """Ignore empty lines"""
                    line = self.reader.next()
                    for col in line:
                        if col != '':
                            return line
            except:
                return None

    class CURLClient:
        """Client for communicating with the web server"""
        __slots__ = [ 'curl', 'http', 'user', 'password', 'authentication', 'response', 'status' , 'success', 'f'] 

        def __init__(self, user, password, authentication='basic', host='psoc.isi.edu'):
            self.http = "http://%s/tagfiler" % host
            self.user = user
            self.password = password
            self.authentication = authentication
            self.response = None
            self.status = 200
            self.success = [ 200, 201, 303 ]
            
            self.curl = pycurl.Curl()
            self.curl.setopt(pycurl.USERPWD, "%s:%s" % (self.user, self.password))
            self.curl.setopt(pycurl.WRITEFUNCTION, self.writecallback)
            
            if authentication == 'basic':
                self.curl.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
            elif authentication == 'digest':
                self.curl.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_DIGEST)
                
            
        def writecallback(self, buf):
            self.response = buf

        def readcallback(self, size):
            buf = self.f.read(size)
            return buf

        def getResponse(self):
            return self.response

        def getStatus(self):
            return self.status

        def getTagdef(self, tag):
            """Get the tag definition"""
            self.curl.setopt(pycurl.URL, "%s/tagdef/%s" % (self.http, urlquote(tag)))
            self.curl.setopt(pycurl.HTTPGET, 1)
            self.response = None
            self.curl.perform()
            self.status = self.curl.getinfo(pycurl.HTTP_CODE)
            
            if self.status not in self.success:
                print "ERROR: %s, Can not get definition for tag '%s'" % (self.status, tag)
                return self.status
            else:
                return 0

        def uploadPOST(self, dataset, file):
            """Upload the dataset file"""
            print "Dataset '%s': [Uploading '%s']" % (dataset, file)
            url = "%s/file/%s" % (self.http, urlquote(dataset))
            self.curl.setopt(pycurl.URL, url)
            self.curl.setopt(pycurl.POST, 1)
            self.curl.setopt(pycurl.HTTPPOST, [('file1', (pycurl.FORM_FILE, file))])
            self.response = None
            self.curl.perform()
            self.status = self.curl.getinfo(pycurl.HTTP_CODE)
            
            if self.status not in self.success:
                print "ERROR: %s, Can not post dataset '%s'" % (self.status, dataset)
                return self.status
            else:
                return 0

        def upload(self, dataset, file):
            """Upload the dataset file"""
            print "Dataset '%s': [Uploading '%s']" % (dataset, file)
            self.f = open(file, 'rb')
            fs = os.path.getsize(file)
            self.curl.setopt(pycurl.READFUNCTION, self.readcallback)
            url = "%s/file/%s" % (self.http, urlquote(dataset))
            self.curl.setopt(pycurl.URL, url)
            self.curl.setopt(pycurl.INFILESIZE, int(fs))
            self.curl.setopt(pycurl.UPLOAD, 1)
            self.response = None
            self.curl.perform()
            self.f.close()
            self.curl.setopt(pycurl.UPLOAD, 0)
            self.status = self.curl.getinfo(pycurl.HTTP_CODE)
            
            if self.status not in self.success:
                print "ERROR: %s, Can not post dataset '%s'" % (self.status, dataset)
                return self.status
            else:
                return 0

        def register(self, dataset, file):
            """Register a directory"""
            print "Dataset '%s': [Registering '%s']" % (dataset, file)
            url = "%s/file/%s" % (self.http, urlquote(dataset))
            self.curl.setopt(pycurl.URL, url)
            self.curl.setopt(pycurl.POST, 1)
            pf = []
            pf.append(('action', 'put'))
            pf.append(('url', file))
            self.curl.setopt(pycurl.HTTPPOST, pf)
            self.response = None
            self.curl.perform()
            self.status = self.curl.getinfo(pycurl.HTTP_CODE)
            
            if self.status not in self.success:
                print "ERROR: %s, Can not post dataset %s" % (self.status, dataset)
                return self.status
            else:
                return 0

        def addTag(self, dataset, tag, value):
            """POST a tag value to a dataset"""
            url = "%s/tags/%s" % (self.http, urlquote(dataset))
            self.curl.setopt(pycurl.URL, url)
            self.curl.setopt(pycurl.POST, 1)
            pf = []
            pf.append(('action', 'put'))
            pf.append(("set-%s" % tag, 'true'))
            if value:
                pf.append(("val-%s" % tag, value))
            self.curl.setopt(pycurl.HTTPPOST, pf)
            self.response = None
            self.curl.perform()
            self.status = self.curl.getinfo(pycurl.HTTP_CODE)
            #print 'Exit'
            #sys.exit()
            #print 'After Exit'
            
            if self.status not in self.success:
                return self.status
            else:
                return 0

        def addTags(self, dataset, values):
            """PUT tags to a dataset"""
            body = StringIO.StringIO(values)
            self.curl.setopt(pycurl.READFUNCTION, body.read)
            url = "%s/tags/%s" % (self.http, urlquote(dataset))
            self.curl.setopt(pycurl.URL, url)
            self.curl.setopt(pycurl.UPLOAD, 1)
            self.curl.setopt(pycurl.HTTPHEADER, ['Content-Type: application/x-www-form-urlencoded'])
            self.curl.setopt(pycurl.INFILESIZE, len(values))
            self.response = None
            self.curl.perform()
            self.status = self.curl.getinfo(pycurl.HTTP_CODE)
            self.curl.setopt(pycurl.UPLOAD, 0)
            self.curl.setopt(pycurl.HTTPHEADER, [])
            
            if self.status not in self.success:
                return self.status
            else:
                return 0

    class Dataset:
        """Class for dataset propertiies"""
        __slots__ = [ 'name' ,'file' ,'tags' ] 

        def __init__(self, name, file, tags):
            self.name = name
            self.file = file
            self.tags = tags

        def add(self, tag, value):
            """Add a tag"""
            if tag not in self.tags:
                self.tags[tag] = set()
            self.tags[tag].add(value)
            
        def iteritems(self):
            return self.tags.iteritems()
        
        def __repr__(self):
            """String representation"""
            return "{name: '%s', file: '%s', Tags: %s}" % (self.name, self.file, self.tags)

def main(argv):
    """Extract parameters from command line"""
    
    parser = OptionParser()
    parser.add_option('-u', '--user', action='store', dest='user', type='string', default='anonymous', help='user for web server authentication (default: \'%default\')')
    parser.add_option('-p', '--password', action='store', dest='password', type='string', default='anonymous', help='password for web server authentication (default: \'%default\')')
    parser.add_option('-H', '--host', action='store', dest='host', type='string', default='psoc.isi.edu', help='host for web server (default: \'%default\')')
    parser.add_option('-a', '--authentication', action='store', dest='authentication', type='string', default='basic', help='authentication type for web server (default: \'%default\')')
    parser.add_option('-f', '--file', action='store', dest='file', type='string', default='', help='CSV file name (default: \'%default\')')
    
    (options, args) = parser.parse_args()

    """Upload the files"""
    csvclient = CSVClient(options.file, options.user, options.password, host=options.host, authentication=options.authentication)
    csvclient.upload()
    
    if csvclient.status == 0:
        print "\nSuccessfully uploaded %s file(s) from '%s'." % (len(csvclient.datasets), options.file)
        
    #csvclient.trace()


if __name__ == '__main__':
    main(sys.argv)
