import matplotlib
matplotlib.use('svg')

from matplotlib import pyplot as plt

import re
import db_driver
import json

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
    print(env.items())
    uri = env['REQUEST_URI']
    thing = parse_thing(uri)
    print(thing)
    history = db.load_history(thing, 'reported')
    senses = list(map(lambda s: {"timestamp": s['timestamp_utc'], "senses": s['state']['senses']}, history))
    if len(senses) > 0:
        sense_types = senses[0]['senses'].keys()
        times = list(map(lambda s: s['timestamp'], senses))

        for sense_type in sense_types:
            values = list(map(float, map(lambda s: s['senses'][sense_type], senses)))
            plt.plot(values, label=sense_type)

    image_location = 'db/%s/graph.png' % thing
    plt.savefig(image_location)
    with open(image_location, 'rb') as f:
        image_bytes = f.read()
    start_response('200 OK', [('Content-Type','image/png')])
    return image_bytes
