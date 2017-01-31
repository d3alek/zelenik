import matplotlib
matplotlib.use('svg')

from matplotlib import pyplot as plt
from matplotlib.dates import date2num, AutoDateLocator, AutoDateFormatter, DateFormatter

import re
import db_driver
import json
import datetime

from dateutil import tz
from urllib import parse

REDIRECT = '<meta http-equiv="refresh" content="0; url=%s" /> %s <a href="%s"> Go back. </a> '
db = db_driver.DatabaseDriver()
timezone = tz.gettz('Europe/Sofia')

def info(method, message):
    print("  uwsgi/%s: %s" % (method, message))

def error(method, message):
    print("! uwsgi/%s: %s" % (method, message))

def parse_thing(uri):
    match = re.match(r'/([a-zA-Z0-9-]+)\/', uri)
    if not match:
        info("parse_thing", "Could not parse thing from uri %s" % uri)
        return ""
    thing = match.group(1)
    return thing

def parse_update_state(uri):
    match = re.match(r'/([a-zA-Z0-9-]+)\/update_(.+)', uri)
    if not match:
        info("parse_update_state", "Could not parse update state from uri %s" % uri)
        return ""
    state = match.group(2)
    return state

def application(env, start_response):
    print(env.items())
    method = env['REQUEST_METHOD']
    uri = env['REQUEST_URI']
    thing = parse_thing(uri)

    if method == 'POST':
        raw_in = env['wsgi.input'].read()
        query = parse.parse_qsl(raw_in)
        state, value = query[0]
        state = state.decode('utf-8')
        value = value.decode('utf-8')
        try:
            value_dict = json.loads(value)
        except ValueError:
            error("application", "Could not parse json value. %s %s %s" % (thing, state, value))
            start_response('200 OK', [('Content-Type','text/html')])
            return ('Could not parse json value %s. %s %s' % (state, thing, value)).encode('utf-8')
        
        if state == 'desired': 
            db.update_desired(thing, value_dict)
        elif state == 'aliases':
            db.update_aliases(thing, value_dict)
        else:
            start_response('200 OK', [('Content-Type','text/plain')])
            return ('Not allowed to change state %s. %s %s' % (state, thing, value)).encode('utf-8')

        start_response('200 OK', [('Content-Type','text/html')])
        back_url = ('/' + thing)
        return (REDIRECT % (back_url, 'Success.', back_url)).encode('utf-8')

    history = db.load_history(thing, 'reported', since_days=1)
    times = list(map(lambda s: db_driver.parse_isoformat(s['timestamp_utc']), history))
    plot_times = list(map(lambda t: date2num(t), times))
    senses = list(map(lambda s: s['state']['senses'], history))
    fig = plt.figure(figsize=(12, 6), dpi=100)
    axes = plt.axes()
    locator = AutoDateLocator(tz=timezone)
    axes.xaxis.set_major_locator(locator)
    axes.xaxis.set_major_formatter(AutoDateFormatter(locator, tz=timezone))
    if len(senses) > 0:
        sense_types = sorted(senses[0].keys())

        for sense_type in sense_types:
            alias = ""
            values = []
            for sense_state in senses:
                value = sense_state[sense_type]
                if type(value) is dict:
                    values.append(float(value['value']))
                    alias = value['alias']
                else:
                    values.append(float(value))

            if alias == "":
                label = sense_type
            else: 
                label = alias
            plt.plot(plot_times, values, label=label)

    axes.autoscale()
    image_location = 'db/%s/graph.png' % thing
    # top of plot, based on example from http://matplotlib.org/users/legend_guide.html
    plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
                       ncol=3, mode="expand", borderaxespad=0.)
    plt.savefig(image_location, dpi=100)
    with open(image_location, 'rb') as f:
        image_bytes = f.read()
    start_response('200 OK', [('Content-Type','image/png')])
    return image_bytes
