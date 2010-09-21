import web
import sys
import os
import sys

# Uncomment the below line in case of a RPM installation
from tagfiler import url_lex, url_parse, url_parse_func

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
            ast = None
        except:
            web.debug('unknown parse error on URI %s' % uri)
            ast = None
            raise
        if ast != None:
            return (uri, ast)
        else:
            raise web.BadRequest()

    # is there some fancier way to do this via introspection
    # in one generic method?
    def HEAD(self):
        uri, ast = self.prepareDispatch()
        if not hasattr(ast, 'HEAD'):
            raise web.NoMethod()
        ast.preDispatch(uri)
        result = ast.HEAD(uri)
        ast.postDispatch(uri)
        return result

    def GET(self):
        uri, ast = self.prepareDispatch()
        if not hasattr(ast, 'GET'):
            raise web.NoMethod()
        ast.preDispatch(uri)
        result = ast.GET(uri)
        ast.postDispatch(uri)
        return result

    def PUT(self):
        uri, ast = self.prepareDispatch()
        if not hasattr(ast, 'PUT'):
            raise web.NoMethod()
        ast.preDispatch(uri)
        result = ast.PUT(uri)
        ast.postDispatch(uri)
        return result

    def DELETE(self):
        uri, ast = self.prepareDispatch()
        if not hasattr(ast, 'DELETE'):
            raise web.NoMethod()
        ast.preDispatch(uri)
        result = ast.DELETE(uri)
        ast.postDispatch(uri)
        return result

    def POST(self):
        uri, ast = self.prepareDispatch()
        if not hasattr(ast, 'POST'):
            raise web.NoMethod()
        ast.preDispatch(uri)
        result = ast.POST(uri)
        ast.postDispatch(uri)
        return result

# this creates the WSGI app from the urls map
application = web.application(urls, globals()).wsgifunc() 

if __name__ == "__main__":
		# Comment the below line in case of a RPM installation
        # sys.path.append(os.path.dirname(sys.argv[0]))
        
	# Comment the below line in case of a RPM installation
	# import url_parse
	url_parse.make_parse()
