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
    error('extract_value', 'Expected value to be either a number or a dict with value number or marked as wrong, got %s instead.' % value_json)
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

