import web

# we need to pick up the deployed app files
import sys
sys.path.append('/var/www/dataserv')

# we short-circuit the web.py regexp dispatch rule, because we need to
# work with REQUEST_URI to get undecoded URI w/ escape sequences.
#

urls = (
    '.*', 'Dispatcher'
)

# instantiate our custom URL parse routine, which returns active
# AST nodes that implement the web.py HTTP methods
import url_parse

from dataserv_app import NotFound

urlparse = url_parse.make_parse()

class Dispatcher:
    def prepareDispatch(self):
        """computes web dispatch from REQUEST_URI

           with the HTTP method of the request, e.g. GET, PUT,
           DELETE...
        """
        uri = web.ctx.env['REQUEST_URI']
        web.debug(uri)
        try:
            ast = urlparse(uri)
            web.debug(ast)
            return (uri, ast)
        except:
            raise NotFound("URI %s not recognized." % uri )


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
