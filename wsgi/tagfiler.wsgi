
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
import sys
import traceback

# Uncomment the below line in case of a RPM installation
from tagfiler import url_lex, url_parse, url_parse_func, dataserv_app

# need to find our other local modules

# we short-circuit the web.py regexp dispatch rule, because we need to
# work with REQUEST_URI to get undecoded URI w/ escape sequences.
#

urls = (
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
            ast = url_parse_func(uri)
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
        uri, ast = self.prepareDispatch()
        if not hasattr(ast, methodname):
            raise web.NoMethod()
        ast.preDispatch(uri)
        astmethod = getattr(ast, methodname)

        try:
            result = astmethod(uri)
            return result
        except dataserv_app.WebException, e:
            if hasattr(e, 'detail'):
                web.header('X-Error-Description', e.detail)
            raise e

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
