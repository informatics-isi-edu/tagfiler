
"""
This is a test/benchmark utility.  See the docstring for the main() function below.

"""

import os
import sys
import urllib
import httplib
import datetime
import pytz



def urlquote(x):
    if hasattr(x, 'items'):
        return '&'.join( '%s=%s' % (urlquote(k), urlquote(v))
                         for k, v in x.items() )
    elif type(x) == tuple:
        k, v = x
        return '%s=%s' % (urlquote(k), urlquote(v))

    elif type(x) in [ bool, int, float ]:
        return urlquote( '%s' % x )
    else:
        return urllib.quote(x)

class CookieJar (dict):
    def __init__(self, cookiefilename=None):
        dict.__init__(self)
        self.cookiefilename = cookiefilename
        if cookiefilename:
            f = open(cookiefilename, 'r+b')
            for line in f:
                if line.strip() == '' or line.strip()[0] == '#':
                    continue
                #print line.strip()
                domain, ignore1, path, ignore2, ignore3, name, value = line.strip().split('\t')
                dict.__setitem__(self, (domain, path, name), value)

    def __setitem__(self, k, v):
        # TODO: fix this to do proper domain/path matching on prefix/suffix
        if self.get(k, None) != v:
            dict.__setitem__(self, k, v)

    def write(self, filename=None):
        if filename == None:
            filename = self.cookiefilename
        if filename:
            f = open(filename, 'w+b')
            f.write('# Netscape HTTP Cookie File\n')
            f.write('# This file was generated by myhttp.py\n')
            for k, v in self.items():
                domain, path, name = k
                f.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (domain, 'FALSE', path, 'TRUE', '0', name, v))

    def getcookies(self, reqdomain, requri):
        cookies = []
        for k, v in self.items():
            domain, path, name = k
            domlen = len(domain)
            reqdomlen = len(reqdomain)
            if domlen > reqdomlen or reqdomain[reqdomlen-domlen:] != domain:
                continue
            urilen = len(requri)
            pathlen = len(path)
            if urilen < pathlen or requri[0:pathlen] != path:
                continue
            cookies.append( "%s=%s" % (name, v) )
        #print '%s.getcookies(%s, %s) = %s' %  (self, reqdomain, requri, cookies)
        return cookies

    def setcookies(self, domain, cookies=[]):
        def parampair(paramparts):
            if len(paramparts) == 1:
                return (paramparts[0].lower(), None)
            else:
                return (paramparts[0].lower(), paramparts[1])

        for cookiestr in cookies:
            #sys.stderr.write('cookiestr: "%s"\n' % cookiestr)
            name, rest = cookiestr.strip().split('=', 1)
            value, rest = rest.split(';', 1)
            params = dict([ parampair(part.strip().split('=', 1)) for part in rest.split(';') ])
            path = params.get('path', '/') # BUG, should be current uri path?
            self[(domain, path, name)] = value


class TagfilerDefaultConnection (httplib.HTTPSConnection):

    def __init__(self, host, catid, cookiejarfile):
        httplib.HTTPSConnection.__init__(self, host)
        self.cookiejar = CookieJar(cookiejarfile)
        self.host = host
        self.catid = int(catid)

    def cookies_write(self):
        self.cookiejar.write()

    def request(self, method, url, body=None, headers=None):
        if headers is None:
            headers = dict()

        if self.cookiejar:
            cookies = headers.get('cookie', []) + self.cookiejar.getcookies(self.host, url)
            if cookies:
                headers['cookie'] = ';'.join(cookies)

        #sys.stderr.write('headers: %s\n' % headers)

        return httplib.HTTPSConnection.request(self, method, url, body, headers)


    def getresponse(self):
        response = httplib.HTTPSConnection.getresponse(self)
        
        cookies =  response.getheader('set-cookie', [])
        if type(cookies) != list:
            cookies = [ cookies ]
        self.cookiejar.setcookies(self.host, cookies)

        return response


    def session_start(self, username, password):
        body = urlquote(dict(username=username, password=password))

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Content-Length': len(body)
            }

        self.request('POST', "/tagfiler/session", body, headers)
        return self.getresponse()


    def session_end(self):
        self.request('DELETE', "/tagfiler/session")
        return self.getresponse()


    def content_request(self, method, url, body=None, headers=None):
        return self.request(method, ("/tagfiler/catalog/%d" % self.catid) + url, body, headers)

    def tagdef_create(self, tagname, dbtype='text', unique=False, multivalue=False, readpolicy='anonymous', writepolicy='subject', tagref=None, soft=False):
        self.content_request(
            'POST', 
            "/tagdef/%s?%s" % (
                urlquote(tagname),
                urlquote(
                    dict(
                        dbtype=dbtype,
                        unique=unique,
                        multivalue=multivalue,
                        readpolicy=readpolicy,
                        writepolicy=writepolicy,
                        tagref=tagref,
                        soft=soft
                        )
                    )
                )
            )
        
        return self.getresponse()


    def tagdef_delete(self, tagname):
        self.content_request('DELETE', "/tagdef/%s" % urlquote(tagname))
        return self.getresponse()


def main(argv):
    """usage: hostname catid [username password]

       Run a test sequence against https://HOSTNAME/tagfiler/catalog/CATID/

       Environment variables:

       HTTP_COOKIEJAR filename where cookies are stored

       LOAD_FILE filename where CSV input data is found
       LOAD_TAGS escaped tagname list for data load URI

       TEST_STRIDE number of rows to load between test cycles
       TEST_SIZES list of numbers of rows to test per inner test cycle
       TEST_CYCLES number of times to repeat inner test cycle

       Usage:

       LOAD_TAGS such as "tag1;tag2;tag3;tag4" 

       LOAD_FILE a CSV table such as:

          key1,val,val,val
          key2,val,val,val
          ...

       where tag1=key1 identifies the first row and tag1=key2
       identifies the second row, so it can be sent to the server
       like:

          POST /subject/tag1(tag1;tag2;tag3;tag4)
          Content-Type: text/csv

          key1,val,val,val
          key2,val,val,val
          ...

    """
    
    try:
        cookiejar = os.environ['HTTP_COOKIEJAR']
    except:
        cookiejar = 'cookies'

    assert len(argv) >= 3, "required arguments: hostname catid"
    hostname, catid = argv[1:3]

    loadfilename = os.environ['LOAD_FILE']
    loadfile = open(loadfilename, 'r')

    loadtags = os.environ.get('LOAD_TAGS', 'tweet;posted_time;body;hashtag_mention')
    loadtags = loadtags.split(';')

    stride_size = int( os.environ.get('TEST_STRIDE', 1) )
    test_sizes = [ int(x) for x in os.environ.get('TEST_SIZES', '1').split() ]
    test_cycles = int( os.environ.get('TEST_CYCLES', 1) )

    c = TagfilerDefaultConnection(hostname, catid, cookiejar)

    if len(argv) >= 5:
        username, password = argv[3:5]
        response = c.session_start(username, password)
        response.read()
        response.close()
        c.cookies_write()

    stridenum = 0

    print 'hostname,graphsize' + ''.join([ ',PUT %d,GET %d, DEL %d' % (s, s, s) for s in test_sizes ])

    while True:
        eof = False

        # read data for one stride into a buffer
        lines = []
        lineno = 0
        while lineno < stride_size:
            line = loadfile.readline()
            if line:
                lines.append( line )
            else:
                eof = True
                break
            lineno += 1

        # get current top of graph so we can reset
        c.content_request('GET', '/subject/id(id)id:desc:?limit=1', headers=dict(accept='text/csv'))
        response = c.getresponse()
        assert response.status == 200, "%s status getting max subject ID prior to load cycle" % response.status
        prev_max_id = int( response.read() )
        response.close()
        
        # run tests at this stride position
        for cycle in range(0, test_cycles):

            results = [ hostname, '%d' % (stride_size * stridenum) ]

            for size in test_sizes:
                if len(lines) < size:
                    continue
    
                test_lines = lines[0:size]
                body = ''.join(test_lines)

                t0 = datetime.datetime.now(pytz.timezone('UTC'))

                # do PUT test
                c.content_request(
                    'POST', 
                    '/subject/%s(%s)' % (loadtags[0], ';'.join(loadtags)),
                    body,
                    { 
                        'Accept': 'text/csv',
                        'Content-Type': 'text/csv',
                        'Content-Length': str( len(body) )
                        }
                    )
                response = c.getresponse()
                assert response.status == 204, "putting test data"
                response.read()
                response.close()

                t1 = datetime.datetime.now(pytz.timezone('UTC'))
                results.append( '%d.%3.3d' % ((t1 - t0).seconds, (t1 - t0).microseconds / 1000) )

                t0 = datetime.datetime.now(pytz.timezone('UTC'))

                # do GET test
                c.content_request(
                    'GET',
                    '/subject/%s;id:gt:%d(%s)?limit=none' % (loadtags[0], prev_max_id, ';'.join(loadtags)),
                    headers={ 
                        'Accept': 'text/csv',
                        'Content-Length': 0
                        }
                    )
                response = c.getresponse()
                assert response.status == 200, "getting test data"
                test_result = response.read()
                response.close()
                get_size = len( test_result.split('\n') ) - 1
                assert get_size == size, "get size %d for test size %d" % (get_size, size)

                t1 = datetime.datetime.now(pytz.timezone('UTC'))
                results.append( '%d.%3.3d' % ((t1 - t0).seconds, (t1 - t0).microseconds / 1000) )

                t0 = datetime.datetime.now(pytz.timezone('UTC'))

                # do DELETE test
                c.content_request(
                    'DELETE',
                    '/subject/%s;id:gt:%d' % (loadtags[0], prev_max_id),
                    headers={ 
                        'Content-Length': 0
                        }
                    )
                response = c.getresponse()
                assert response.status == 204, "deleting test data"
                response.read()
                response.close()
            
                t1 = datetime.datetime.now(pytz.timezone('UTC'))
                results.append( '%d.%3.3d' % ((t1 - t0).seconds, (t1 - t0).microseconds / 1000) )

            print ','.join(results)

        # load stride data to make graph larger
        body = ''.join(lines)
        c.content_request(
            'POST',
            '/subject/%s(%s)' % (loadtags[0], ';'.join(loadtags)),
            body,
            { 
                'Content-Type': 'text/csv',
                'Content-Length': str(len(body))
                }
            )
        response = c.getresponse()
        assert response.status == 204, "putting stride data"
        response.read()
        response.close()

        if eof:
            break

        stridenum += 1

    c.cookies_write()
    
    
if __name__ == "__main__":
    sys.exit( main(sys.argv) )
