import os
from jinja2 import Environment, PackageLoader
from lxml import objectify, html
from lxml.objectify import E

def deannotate(fn):
    def wrap(*args, **kwargs):
        if 'tostring' in kwargs:
            tostring = kwargs.pop('tostring')
        else:
            tostring = False
        obj = fn(*args, **kwargs)
        objectify.deannotate(obj, cleanup_namespaces=True)
        if tostring:
            return html.tostring(obj)
        return obj
    return wrap

class HTML(object):
    def __init__(self, package_name='data_server', folder='templates'):
        self.env = Environment(loader=PackageLoader(package_name, folder))
        self.html = E.html()

    def init(self, title=None, style=None, **body):
        self.html = E.html(E.head(), E.body(E.div(), **body))
        self.html.body.div.set('class', 'container')
        if title:
            self.html.head.append(E.title(title))
        if style:
            self.html.head.append(E.style(style, type='text/css'))

    @staticmethod
    def from_element(html):
        return objectify.XML(html)

    def from_html(self, html):
        self.html = self.from_element(html)

    @deannotate
    def generate_table(self, col, **kwargs):
        table = E.table(**kwargs)
        for attr, value in col:
            table.append(E.tr(E.td(value, **attr))) 
        return table

    @deannotate
    def element(self, name, *args, **kwargs):
        klass = None
        if 'class_' in kwargs:
            klass = kwargs.pop('class_')
        if 'klass' in kwargs:
            klass = kwargs.pop('klass')
        element = getattr(E, name)(*args, **kwargs)
        if klass:
            element.set('class', klass)
        return element

    def to_html(self):
        objectify.deannotate(self.html, cleanup_namespaces=True)
        return html.tostring(self.html, pretty_print=True)

    def render_template(self, name, **kwargs):
        return self.env.get_template(name).render(**kwargs)
