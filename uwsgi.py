import re
import db_driver
import datetime
import cgi

import gui_update
import graph

import urllib.parse

db = db_driver.DatabaseDriver()
UPDATEABLE = set(['reported', 'desired', 'displayables', 'thing-alias'])

def info(method, message):
    print("  uwsgi/%s: %s" % (method, message))

def parse_thing(url_path):
    match = re.match(r'/(db|na)/([a-zA-Z0-9-]+)\/', url_path)
    if not match:
        info("parse_thing", "Could not parse thing from url path %s" % url_path)
        return None
    thing = match.group(2)
    return thing

def parse_post_action(url_path):
   return url_path.split('/')[-1]

def parse_graph_attributes(url_path):
    match = re.match(r'/(db|na)/([a-zA-Z0-9-]+)\/graph-([0-9]*)-median-([0-9]*)(-w)?', url_path)
    if not match:
        info("parse_graph_attributes", "Could not parse graph attributes from url_path %s. Default to 1" % url_path)
        return 1, 1
    since_days = int(match.group(3))
    median_kernel = int(match.group(4))
    if median_kernel % 2 != 1:
        median_kernel += 1
    if match.group(5) == '-w':
        wrongs = True
    else:
        wrongs = False


    return since_days, median_kernel, wrongs

def application(env, start_response):
    method = env['REQUEST_METHOD']
    raw_uri = env['REQUEST_URI']

    url = urllib.parse.urlparse(raw_uri)
    queries = urllib.parse.parse_qs(url.query)

    thing = parse_thing(url.path)

    content_type = None
    data = None
    if not thing:
        start_response('200 OK', [('Content-Type', "text/plain")])
        data = "Could not parse thing from uri %s" % raw_uri
        data = data.encode('utf-8')
        return data

    if method == 'POST':
        formdata = cgi.FieldStorage(environ=env, fp=env['wsgi.input'])
        action = parse_post_action(url.path)
        if action == "update":
            if 'plot' in formdata and formdata['plot'].filename != '':
                file_data = formdata['plot'].file.read()

                content_type, data = gui_update.update_plot_background(db, thing, file_data)

            to_update = UPDATEABLE.intersection(formdata.keys())

            for state in to_update:
                content_type, data = gui_update.handle_update(db, thing, state, formdata[state].value, queries.get('ret', [None])[0])
        elif action == "graph":
            content_type, data = graph.handle_graph(db, thing, formdata=formdata)
        else:
            error("application", "Unexpected POST action %s" % action)
    else:
        since_days, median_kernel, wrongs = parse_graph_attributes(url.path)
        content_type, data = graph.handle_graph(db, thing, since_days, median_kernel, wrongs)

    if content_type is None or data is None:
        content_type = "text/html"
        data = gui_update.HTML % "Нищо за вършене."

    start_response('200 OK', [('Content-Type', content_type)])
    if 'text' in content_type:
        data = data.encode('utf-8')
    return data

