import re
import db_driver
import datetime
import cgi

import gui_update
import graph

db = db_driver.DatabaseDriver()
UPDATEABLE = set(['reported', 'desired', 'displayables', 'thing-alias'])

def info(method, message):
    print("  uwsgi/%s: %s" % (method, message))

def parse_thing(uri):
    match = re.match(r'/(db|na)/([a-zA-Z0-9-]+)\/', uri)
    if not match:
        info("parse_thing", "Could not parse thing from uri %s" % uri)
        return None
    thing = match.group(2)
    return thing

def parse_graph_attributes(uri):
    match = re.match(r'/(db|na)/([a-zA-Z0-9-]+)\/graph-([0-9]*)-median-([0-9]*)', uri)
    if not match:
        info("parse_graph_attributes", "Could not parse graph attributes from uri %s. Default to 1" % uri)
        return 1, 1
    since_days = int(match.group(3))
    median_kernel = int(match.group(4))
    if median_kernel % 2 != 1:
        median_kernel += 1

    return since_days, median_kernel

def application(env, start_response):
    method = env['REQUEST_METHOD']
    uri = env['REQUEST_URI']
    thing = parse_thing(uri)

    content_type = None
    data = None
    if not thing:
        start_response('200 OK', [('Content-Type', "text/plain")])
        data = "Could not parse thing from uri %s" % uri
        data = data.encode('utf-8')
        return data

    if method == 'POST':
        formdata = cgi.FieldStorage(environ=env, fp=env['wsgi.input'])

        if 'plot' in formdata and formdata['plot'].filename != '':
            file_data = formdata['plot'].file.read()

            content_type, data = gui_update.update_plot_background(db, thing, file_data)

        to_update = UPDATEABLE.intersection(formdata.keys())

        for state in to_update:
            content_type, data = gui_update.handle_update(db, thing, state, formdata[state].value)

    else:
        since_days, median_kernel = parse_graph_attributes(uri)
        content_type, data = graph.handle_graph(db, thing, since_days, median_kernel)

    if content_type is None or data is None:
        content_type = "text/html"
        data = gui_update.HTML % "Нищо за вършене."

    start_response('200 OK', [('Content-Type', content_type)])
    if 'text' in content_type:
        data = data.encode('utf-8')
    return data

