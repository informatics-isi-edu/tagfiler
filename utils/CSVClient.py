#!/usr/bin/python

import csv
import sys
import pycurl
import os
import traceback
import urllib
from optparse import OptionParser

def urlquote(url):
    """define common URL quote mechanism for registry URL value embeddings"""
    return urllib.quote(url, safe='')

class CSVClient:
    """Class for uploading datasets from CSV files"""
    __slots__ = [ 'csvname', 'user', 'password', 'host', 'authentication', 'csvreader', 'curlclient', 'tags', 'tagdefs', 'tagindex', 'datasetindex', 'fileindex', 'datasets', 'status' ] 

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
            self.curlclient.getTagdef(tag)
            if self.curlclient.status != 200:
                print 'ERROR: Can not get definition for tag \'' + tag + '\'.'
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
        if os.path.isfile(row[0]) == False:
            print 'ERROR: File \'' + row[0] + '\' does not exist.'
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
            """Set the dataset name"""
            if row[self.datasetindex] != '':
                name = row[self.datasetindex]
            else:
                name = os.path.basename(row[0])
            dataset = self.Dataset(name, row[0])
            self.datasets[name] = dataset
            """Set the dataset tags"""
            while True:
                for i in range(self.tagindex,len(row)):
                    if row[i]:
                        dataset.add(self.tags[i-self.tagindex], row[i])
                try:
                    row = self.csvreader.readline()
                    if row[0] and row[0] != '':
                        return row
                except:
                    return None

    def validateTagsValues(self):
        """Validate tags values"""
        for dataset, datasetdefs in self.datasets.iteritems():
            for tag, tagvalues in datasetdefs.iteritems():
                if len(tagvalues) > 1 and self.tagdefs[tag]['multivalue'] == 'False':
                    print 'ERROR: Tag \'' + tag + '\' in dataset \'' + dataset + '\' is not allowed to have multiple values.'
                    self.status = 1
        
    def postDatasets(self):
        """Post the datasets"""
        for dataset, datasetdefs in self.datasets.iteritems():
            """Upload the dataset file"""
            self.curlclient.upload(dataset, datasetdefs.file)
            """Post the dataset tags"""
            for tag, tagvalues in datasetdefs.iteritems():
                try:
                    self.tagdefs[tag]['typestr']
                    """Tag with values"""
                    for value in tagvalues:
                        self.curlclient.addTag(dataset, tag, value)
                except:
                    """Tag without values"""
                    self.curlclient.addTag(dataset, tag, None)
        
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
                print 'Can not open file ' + csvname
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
        __slots__ = [ 'curl', 'http', 'user', 'password', 'authentication', 'response', 'status' ] 

        def __init__(self, user, password, authentication='basic', host='psoc.isi.edu'):
            self.http = 'http://' + host + '/tagfiler'
            self.user = user
            self.password = password
            self.authentication = authentication
            self.response = None
            self.status = 200
            
            self.curl = pycurl.Curl()
            self.curl.setopt(pycurl.USERPWD, self.user + ':' + self.password)
            self.curl.setopt(pycurl.WRITEFUNCTION, self.writecallback)
            
            if authentication == 'basic':
                self.curl.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
            elif authentication == 'digest':
                self.curl.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_DIGEST)
                
        def writecallback(self, buf):
            self.response = buf

        def getResponse(self):
            return self.response

        def getStatus(self):
            return self.status

        def getTagdef(self, tag):
            """Get the tag definition"""
            self.curl.setopt(pycurl.URL, self.http + '/tagdef/' + urlquote(tag))
            self.curl.setopt(pycurl.HTTPGET, 1)
            self.response = None
            self.curl.perform()
            self.status = self.curl.getinfo(pycurl.HTTP_CODE)

        def upload(self, dataset, file):
            """Upload the dataset file"""
            print 'Dataset \'' + dataset + '\': [Uploading \'' + file +'\']'
            url = self.http + '/file/' + urlquote(dataset)
            self.curl.setopt(pycurl.URL, url)
            self.curl.setopt(pycurl.POST, 1)
            self.curl.setopt(pycurl.HTTPPOST, [('file1', (pycurl.FORM_FILE, file))])
            self.response = None
            self.curl.perform()
            return self.response

        def addTag(self, dataset, tag, value):
            """POST a tag value to a dataset"""
            url = self.http + '/tags/' + urlquote(dataset)
            self.curl.setopt(pycurl.URL, url)
            self.curl.setopt(pycurl.POST, 1)
            pf = []
            pf.append(('action', 'put'))
            pf.append(('set-'+tag, 'true'))
            if value:
                pf.append(('val-'+tag, value))
            self.curl.setopt(pycurl.HTTPPOST, pf)
            self.response = None
            self.curl.perform()
            return self.response

    class Dataset:
        """Class for dataset propertiies"""
        __slots__ = [ 'name' ,'file' ,'tags' ] 

        def __init__(self, name, file):
            self.name = name
            self.file = file
            self.tags = {}

        def add(self, tag, value):
            """Add a tag"""
            if tag not in self.tags:
                self.tags[tag] = set()
            self.tags[tag].add(value)
            
        def iteritems(self):
            return self.tags.iteritems()
        
        def __repr__(self):
            return '{\'file\': \'' + self.file + '\', \'Tags\': ' + str(self.tags) + '}'

def main(argv):
    """Extract parameters from commandline"""
    
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
    #csvclient.trace()


if __name__ == '__main__':
    main(sys.argv)
