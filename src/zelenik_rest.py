from flask import Flask, request, json
from datetime import datetime, timedelta
import csv
from io import StringIO
from pathlib import Path
import sys
root_path = Path(__file__).absolute().parent.parent
sys.path.append(str(root_path))

from db_driver import DatabaseDriver, flat_map, timestamp

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
    since_argument = request.args.get('since', None)
    if since_argument:
        try:
            since_days = int(since_argument)
        except ValueError:
            abort(400) # Bad Request
    else:
        since_days = 1

    history = db.load_history(a_thing, "reported", since_days=since_days)

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


