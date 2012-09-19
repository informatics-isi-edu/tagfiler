
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

import web
import sys
import os
import traceback
import itertools
import urllib
import datetime
import pytz

# Uncomment the below line in case of a RPM installation
from tagfiler import url_lex, url_parse, dataserv_app

# need to find our other local modules

# we short-circuit the web.py regexp dispatch rule, because we need to
# work with REQUEST_URI to get undecoded URI w/ escape sequences.
#

UserSession = dataserv_app.webauthn2_handler_factory.UserSession
UserPassword = dataserv_app.webauthn2_handler_factory.UserPassword
UserManage = dataserv_app.webauthn2_handler_factory.UserManage
AttrManage = dataserv_app.webauthn2_handler_factory.AttrManage
AttrAssign = dataserv_app.webauthn2_handler_factory.AttrAssign
AttrNest = dataserv_app.webauthn2_handler_factory.AttrNest

urls = (
    '/session(/[^/]+)', UserSession,
    '/session()', UserSession,
    '/password(/[^/]+)', UserPassword,
    '/password()', UserPassword,
    '/user(/[^/]+)', UserManage,
    '/user()', UserManage,
    '/attribute(/[^/]+)', AttrManage,
    '/attribute()', AttrManage,
    '/user/([^/]+)/attribute(/[^/]+)', AttrAssign,
    '/user/([^/]+)/attribute()', AttrAssign,
    '/attribute/([^/]+)/implies(/[^/]+)', AttrNest,
    '/attribute/([^/]+)/implies()', AttrNest,
    
    '.*', 'Dispatcher'
    )

# instantiate our custom URL parse routine, which returns active
# AST nodes that implement the web.py HTTP methods


class Dispatcher:
    def prepareDispatch(self):
        """computes web dispatch from REQUEST_URI

           with the HTTP method of the request, e.g. GET, PUT,
           DELETE...
        """
        # NOTE: we need this threaded dictionary not available until
        # we start dispatching!
        # Comment the below line in case of a RPM installation
        # sys.path.append(os.path.dirname(web.ctx.env['SCRIPT_FILENAME']))

        uri = web.ctx.env['REQUEST_URI']

        try:
            ast = url_parse.url_parse_func(uri)
        except url_lex.LexicalError, te:
            web.debug('lex error on URI %s' % uri)
            ast = None
        except url_parse.ParseError, te:
            web.debug('parse error on URI %s' % uri)
            #web.debug(traceback.format_exception(TypeError, te, sys.exc_info()[2]))
            ast = None
        except:
            web.debug('unknown parse error on URI %s' % uri)
            ast = None
            raise
        if ast != None:
            return (uri, ast)
        else:
            raise web.BadRequest()

    def METHOD(self, methodname):
        start_time = datetime.datetime.now(pytz.timezone('UTC'))
        
        uri, ast = self.prepareDispatch()
        prepare_time = datetime.datetime.now(pytz.timezone('UTC'))
        if not hasattr(ast, methodname):
            raise web.NoMethod()
        ast.start_time = start_time
        ast.last_log_time = start_time
        ast.preDispatch(uri)
        astmethod = getattr(ast, methodname)
        #ast.log('TRACE', value='Dispatcher::METHOD() after preDispatch')
        try:

            try:
                #web.debug((uri,astmethod))
                #web.debug(('env',web.ctx.env))
                result = astmethod(uri)

                if hasattr(result, 'next'):
                    try:
                        first = result.next()
                    except StopIteration:
                        return result
                    return itertools.chain([first], result)
                else:
                    return result
            except dataserv_app.WebException, e:
                if hasattr(e, 'detail'):
                    detail = dataserv_app.myutf8(e.detail)
                    web.header('X-Error-Description', detail)
                raise e

        finally:
            # log after we force iterator, to flush any deferred transaction log messages
            end_time = datetime.datetime.now(pytz.timezone('UTC'))
            ast.lograw('%d.%3.3ds %s%s req=%s (%s) %s %s://%s%s %s %s' % ((end_time - start_time).seconds,
                                                                         (end_time - start_time).microseconds / 1000, 
                                                                         web.ctx.ip, ast.context.client and ' user=%s' % urllib.quote(ast.context.client) or '',
                                                                         ast and ast.request_guid or '',
                                                                         web.ctx.status, web.ctx.method, web.ctx.protocol, web.ctx.host, uri,
                                                                         ast and ast.content_range and ('%s/%s' % ast.content_range) or '',
                                                                         ast and ast.emitted_headers.get('content-type', '') or ''))

        # ast.postDispatch(uri) # disable since preDispatch/midDispatch are sufficient
        # return result

    def HEAD(self):
        return self.METHOD('HEAD')

    def GET(self):
        return self.METHOD('GET')
        
    def PUT(self):
        return self.METHOD('PUT')

    def DELETE(self):
        return self.METHOD('DELETE')

    def POST(self):
        return self.METHOD('POST')

# this creates the WSGI app from the urls map
application = web.application(urls, globals()).wsgifunc() 

if __name__ == "__main__":
    # Comment the below line in case of a RPM installation
    # sys.path.append(os.path.dirname(sys.argv[0]))
        
    # Comment the below line in case of a RPM installation
    # import url_parse
    url_parse.make_parse()
