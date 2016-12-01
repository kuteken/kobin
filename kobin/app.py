from importlib.machinery import SourceFileLoader
from jinja2 import Environment, FileSystemLoader
import os
import traceback

from .routes import Router
from .environs import request, HTTPError


class Kobin:
    def __init__(self, root_path='.'):
        self.router = Router()
        self.config = Config(os.path.abspath(root_path))

    def route(self, rule=None, method='GET', name=None, callback=None):
        def decorator(callback_func):
            self.router.add(method, rule, name, callback_func)
            return callback_func
        return decorator(callback) if callback else decorator

    def _handle(self, environ):
        environ['kobin.app'] = self
        request.bind(environ)

        try:
            callback, kwargs = self.router.match(environ)
            response = callback(**kwargs) if kwargs else callback()
        except HTTPError as e:
            response = e
        except BaseException as e:
            traceback.print_tb(e.__traceback__)
            if self.config['DEBUG']:
                message = '\n'.join(traceback.format_tb(e.__traceback__))
            else:
                message = 'Internal Server Error'
            response = HTTPError(message, 500)
        return response

    def wsgi(self, environ, start_response):
        response = self._handle(environ)
        start_response(response.status, response.headerlist)
        return response.body

    def __call__(self, environ, start_response):
        """It is called when receive http request."""
        return self.wsgi(environ, start_response)


class Config(dict):
    default_config = {
        'BASE_DIR': os.path.abspath('.'),
        'TEMPLATE_DIRS': [os.path.join(os.path.abspath('.'), 'templates')],
        'DEBUG': False,
    }

    def __init__(self, root_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_path = root_path
        self.update(self.default_config)
        self.update_jinja2_environment()

    def load_from_pyfile(self, file_name):
        file_path = os.path.join(self.root_path, file_name)
        module = SourceFileLoader('config', file_path).load_module()
        self.load_from_module(module)

    def load_from_module(self, module):
        configs = {key: getattr(module, key) for key in dir(module) if key.isupper()}
        self.update(configs)
        self.update_jinja2_environment()

    def update_jinja2_environment(self):
        self['JINJA2_ENV'] = Environment(loader=FileSystemLoader(self['TEMPLATE_DIRS']))


def current_app():
    return request['kobin.app']


def current_config():
    return current_app().config
