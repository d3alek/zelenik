#!/www/zelenik/venv/bin/python

import json
import sys
from pathlib import Path
import getpass

if not getpass.getuser() == 'otselo':
    raise Exception('Should run as user "otselo"')

removed = 0

def to_compact_json(s):
    return json.dumps(s, separators=(',', ':'))

def extract_value(sense):
    if type(sense) is dict:
        value = sense['value']
    else:
        value = sense

    if type(value) is str and value.startswith('w'):
        return 0
    else:
        return float(value)


def remove_sense(j):
    global sense, clamping, removed
    copy = dict(j)
    sense_value = copy['state']['senses'].get(sense, None)
    if sense_value:
        value = extract_value(sense_value)
        if value > clamping:
            copy['state']['senses'].pop(sense, None)
            removed += 1

    return copy

def clear_graphs(thing_directory):
    graphs = [x for x in thing_directory.iterdir() if x.match('graph*.png')]
    if len(graphs) > 0:
        for graph in graphs:
            graph.unlink()

if len(sys.argv) < 5:
    raise Exception("Please provide thing alias and timestamp and sense and clamping value as an argument")
else:
    thing_alias = sys.argv[1]
    timestamp = sys.argv[2]
    sense = sys.argv[3]
    clamping = int(sys.argv[4])
    print("alias: %s, timestamp: %s, sense: %s, clamping value: %d" % (thing_alias, timestamp, sense, clamping))

thing_directory = Path('/www/zelenik/db/na') / thing_alias 
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


clear_graphs(thing_directory)

print("Removed %d" % removed)

print("Does graph look okay? I will delete old reported history if yes or bring it back if no. (yes/No)")
yes_no = input()
if yes_no.lower() == "yes":
    backup.unlink()
    print("Applied changes permanently")
else:
    backup.replace(file)
    clear_graphs(thing_directory)
    print("Reverted changes")

