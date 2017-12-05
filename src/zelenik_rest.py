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

def timestamped_sense_values(state):
    ret = {"timestamp_utc": state.get("timestamp_utc")}
    senses = flat_map(state.get("state", {}).get("senses", {}), "value", strict=True)
    ret.update(senses)
    return ret


"""
Format:

timestamp,sense1,sense2,...,senseN
2017-11-30 22:05:50,30.3,40.1,..,20.2
...

"""
@app.route("/na/<a_thing>/senses", methods=["GET"])
@app.route("/db/<a_thing>/senses", methods=["GET"])
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

    sense_values_history = [*map(timestamped_sense_values, history)]
    all_sense_names = set()
    for sense_values in sense_values_history:
        all_sense_names.update(sense_values.keys())
    all_sense_names.remove("timestamp_utc")

    ordered_sense_names = sorted(list(all_sense_names))
    ordered_sense_names.insert(0, "timestamp_utc")

    s = StringIO()
    writer = csv.DictWriter(s, ordered_sense_names)
    writer.writeheader()
    writer.writerows(sense_values_history)
    return s.getvalue()


