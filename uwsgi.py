import matplotlib
matplotlib.use('svg')

from matplotlib import pyplot as plt
from matplotlib.dates import date2num, AutoDateLocator, AutoDateFormatter, DateFormatter

import re
import db_driver
import json
import datetime

db = db_driver.DatabaseDriver()

def info(method, message):
    print("  uwsgi/%s: %s" % (method, message))

def parse_thing(uri):
    match = re.match(r'/([a-zA-Z0-9-]+)\/', uri)
    if not match:
        info("parse_thing", "Could not parse thing from uri %s" % uri)
        return "", ""
    thing = match.group(1)
    return thing

def application(env, start_response):
    uri = env['REQUEST_URI']
    thing = parse_thing(uri)
    history = db.load_history(thing, 'reported', since_days=1)
    times = list(map(lambda s: db_driver.parse_isoformat(s['timestamp_utc']), history))
    # TODO include tz utc
    plot_times = list(map(lambda t: date2num(t), times))
    senses = list(map(lambda s: s['state']['senses'], history))
    fig = plt.figure(figsize=(12, 6), dpi=100)
    axes = plt.axes()
    locator = AutoDateLocator()
    axes.xaxis.set_major_locator(locator)
    axes.xaxis.set_major_formatter(AutoDateFormatter(locator))#DateFormatter("%H:%M"))
    if len(senses) > 0:
        sense_types = sorted(senses[0].keys())

        for sense_type in sense_types:
            values = list(map(float, map(lambda s: s[sense_type], senses)))
            plt.plot(plot_times, values, label=sense_type)

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
