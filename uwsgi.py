import re
import db_driver
import datetime

from urllib import parse

from gui_update import handle_update
from graph import handle_graph

db = db_driver.DatabaseDriver()

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
        raw_in = env['wsgi.input'].read().decode('utf-8')
        query = parse.parse_qsl(raw_in)
        state, value = query[0]
        state = state
        value = value

        content_type, data = handle_update(db, thing, state, value)
    else:
        since_days = parse_since_days(uri)
        content_type, data = handle_graph(db, thing, since_days)

    start_response('200 OK', [('Content-Type', content_type)])
    if 'text' in content_type:
        data = data.encode('utf-8')
    return data

