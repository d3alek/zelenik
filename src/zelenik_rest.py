from flask import Flask, request, json
from datetime import datetime, timedelta
import csv
import math
from io import StringIO
from pathlib import Path
import sys
root_path = Path(__file__).absolute().parent.parent
sys.path.append(str(root_path))

from db_driver import DatabaseDriver, flat_map, timestamp

GOOD_PERFORMANCE_LENGTH = 300

app = Flask(__name__)
app.config.from_object(__name__)

app.config.update(dict(
    DATABASE=Path(app.root_path).parent
))

def timestamped(state):
    ret = {"timestamp_utc": state.get("timestamp_utc")}
    senses = flat_map(state.get("state", {}).get("senses", {}), "value", strict=True)
    senses = { ("sense(%s)" % key) : value for key, value in senses.items() }
    ret.update(senses)
    writes = state.get("state", {}).get("write", {})
    writes = { ("write(%s)" % key) : value for key, value in writes.items() }
    ret.update(writes)
    return ret

"""
Format:

timestamp,sense(sense1),sense(sense2),...,sense(senseN), write(write1),..., write(writeN)
2017-11-30 22:05:50,30.3,40.1,..,20.2, 0, ..., 1
...

"""
@app.route("/na/<a_thing>/history", methods=["GET"])
@app.route("/db/<a_thing>/history", methods=["GET"])
def history(a_thing):
    db = DatabaseDriver(app.config["DATABASE"])
    since_days_argument = request.args.get('since_days', None)
    since_hours_argument = request.args.get('since_hours', None)
    if not (since_days_argument or since_hours_argument):
        abort(400) # Bad Request

    if since_days_argument:
        try:
            since_days = int(since_days_argument)
        except ValueError:
            abort(400) # Bad Request
    else:
        since_days = 0

    if since_hours_argument:
        try:
            since_hours = int(since_hours_argument)
        except ValueError:
            abort(400) # Bad Request
    else:
        since_hours = 0

    history = db.load_history(a_thing, "reported", since_days=since_days, since_hours=since_hours)
    if len(history) > GOOD_PERFORMANCE_LENGTH:
        rate = math.ceil(len(history) / GOOD_PERFORMANCE_LENGTH) # ceil so we are concervative
        history = history[:-1:rate]

    if not history:
        return b"\r\n"

    values_history = [*map(timestamped, history)]
    all_names = set()
    for values in values_history:
        all_names.update(values.keys())
    all_names.remove("timestamp_utc")

    ordered_names = sorted(list(all_names))
    ordered_names.insert(0, "timestamp_utc")

    s = StringIO()
    writer = csv.DictWriter(s, ordered_names)
    writer.writeheader()
    writer.writerows(values_history)
    return s.getvalue()


