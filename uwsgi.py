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
    match = re.match(r'/db/([a-zA-Z0-9-]+)\/', uri)
    if not match:
        info("parse_thing", "Could not parse thing from uri %s" % uri)
        return ""
    thing = match.group(1)
    return thing

def parse_update_state(uri):
    match = re.match(r'/db/([a-zA-Z0-9-]+)\/update_(.+)', uri)
    if not match:
        info("parse_update_state", "Could not parse update state from uri %s" % uri)
        return ""
    state = match.group(2)
    return state

def application(env, start_response):
    method = env['REQUEST_METHOD']
    uri = env['REQUEST_URI']
    thing = parse_thing(uri)

    if method == 'POST':
        raw_in = env['wsgi.input'].read()
        query = parse.parse_qsl(raw_in)
        state, value = query[0]
        state = state.decode('utf-8')
        value = value.decode('utf-8')

        content_type, url = handle_update(db, thing, state, value)
    else:
        content_type, url = handle_graph(db, thing)

    start_response('200 OK', [('Content-Type', content_type)])
    return url

