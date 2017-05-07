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

def parse_since_days(uri):
    match = re.match(r'/(db|na)/([a-zA-Z0-9-]+)\/graph-?([0-9]*)', uri)
    if not match:
        info("parse_since_days", "Could not parse since_days from uri %s. Default to 1" % uri)
        return 1
    since_days = match.group(3)
    if since_days:
        return int(since_days)
    else:
        return 1

def application(env, start_response):
    method = env['REQUEST_METHOD']
    uri = env['REQUEST_URI']
    thing = parse_thing(uri)

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
        since_days = parse_since_days(uri)
        content_type, data = graph.handle_graph(db, thing, since_days)

    start_response('200 OK', [('Content-Type', content_type)])
    if 'text' in content_type:
        data = data.encode('utf-8')
    return data

