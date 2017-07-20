import sys
sys.path.append('/www/zelenik/')
from db_driver import DatabaseDriver
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from numbers import Number

def error(method, message):
    print("! util/%s: %s" % (method, message))

db = DatabaseDriver(working_directory='/www/zelenik')

def extract_value(value_json):
    if isinstance(value_json, Number):
        return value_json
    elif isinstance(value_json, str) and value_json.startswith('w'):
        return value_json # wrong but let pandas handle it
    elif type(value_json) is dict:
        value = value_json.get('value')
        if isinstance(value, Number):
            return value
        elif isinstance(value, str) and value.startswith('w'):
            return value # wrong but let pandas handle it
    #error('extract_value', 'Expected value to be either a number or a dict with value number or marked as wrong, got %s instead.' % value_json)
    return float("nan")

def flat_map(senses):
    senses.pop("time", None)
    return dict(map(lambda key_value: (key_value[0], extract_value(key_value[1])), senses.items()))

def load_senses(a_thing, since_days=1):
    history = db.load_history(a_thing, 'reported', since_days)
    history_senses = map(lambda s: s['state']['senses'], history)
    history_times = map(lambda s: s['timestamp_utc'], history)
    values = list(map(flat_map, history_senses))

    return pd.DataFrame(values, map(pd.Timestamp, history_times))

def load_write(a_thing, write, since_days=1):
    history = db.load_history(a_thing, 'reported', since_days)
    history_writes = map(lambda s: s['state']['write'], history)
    history_times = map(lambda s: s['timestamp_utc'], history)
    values = list(map(lambda s: extract_value(s.get(write)), history_writes))

    return pd.Series(values, map(pd.Timestamp, history_times), name=write)

# source: https://stackoverflow.com/a/17796231
# m denotes the number of examples here, not the number of features
def gradientDescent(x, y, theta, alpha, m, numIterations):
    x = x.fillna(0)
    y = y.fillna(0)
    xTrans = x.transpose()
    for i in range(0, numIterations):
        hypothesis = np.dot(x, theta)
        loss = hypothesis - y
        # avg cost per example (the 2 in 2*m doesn't really matter here.
        # But to be consistent with the gradient, I include it)
        cost = np.sum(loss ** 2) / (2 * m)
        # print("Iteration %d | Cost: %f" % (i, cost))
        # avg gradient per example
        gradient = np.dot(xTrans, loss) / m
        # update
        theta = theta - alpha * gradient
    return theta

def at_five(s):
    day = s.index[0].day
    month = s.index[0].month
    return s[('2017-%02d-%02d 14:00' % (month, day)):('2017-%02d-%02d 14:30' % (month, day))]

