import web
import sys
import os

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
        sys.path.append(os.path.dirname(web.ctx.env['SCRIPT_FILENAME']))

        # cannot import until we get the import path above!
        import url_parse

        urlparse = url_parse.make_parse()
        uri = web.ctx.env['REQUEST_URI']
        web.debug(uri)

        try:
            ast = urlparse(uri)
        except:
            ast = None
        if ast != None:
            web.debug(ast)
            return (uri, ast)
        else:
            raise web.BadRequest()

    # is there some fancier way to do this via introspection
    # in one generic method?
    def GET(self):
        uri, ast = self.prepareDispatch()
        return ast.GET(uri)

    def PUT(self):
        uri, ast = self.prepareDispatch()
        return ast.PUT(uri)

    def DELETE(self):
        uri, ast = self.prepareDispatch()
        return ast.DELETE(uri)

    def POST(self):
        uri, ast = self.prepareDispatch()
        return ast.POST(uri)

# this creates the WSGI app from the urls map
application = web.application(urls, globals()).wsgifunc() 
