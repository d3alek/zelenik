#!/www/zelenik/venv/bin/python

import json
import sys
from pathlib import Path

removed = 0

def to_compact_json(s):
    return json.dumps(s, separators=(',', ':'))

def remove_sense(j):
    global sense, clamping, removed
    copy = dict(j)
    sense_value = copy['state']['senses'].get(sense, None)
    if sense_value:
        if type(sense_value) is dict:
            value = float(sense_value['value'])
        else:
            value = float(sense_value)
        if value > clamping:
            copy['state']['senses'].pop(sense, None)
            removed += 1

    return copy

if len(sys.argv) < 5:
    raise Exception("Please provide thing alias and timestamp and sense and clamping value as an argument")
else:
    thing_alias = sys.argv[1]
    timestamp = sys.argv[2]
    sense = sys.argv[3]
    clamping = int(sys.argv[4])
    print("alias: %s, timestamp: %s, sense: %s, clamping value: %d" % (thing_alias, timestamp, sense, clamping))

thing_directory = Path('db') / 'na' / thing_alias 
file = thing_directory / 'history' / ("reported.%s.txt" % timestamp)

if not file.exists():
    raise Exception('File %s does not exist' % file)

with file.open() as f:
    lines = f.readlines()

jsons = list(map(json.loads, lines))

processed_jsons = list(map(remove_sense, jsons))

backup = file.with_suffix('.bu')

file.replace(backup)

with file.open('w') as f:
    f.write("\n".join(map(to_compact_json, processed_jsons)));
    f.write("\n")


graphs = [x for x in thing_directory.iterdir() if x.match('graph*.png')]
if len(graphs) > 0:
    for graph in graphs:
        graph.unlink()

print("Removed %d" % removed)
