#!/www/zelenik/venv/bin/python

from pathlib import Path
import json

import sys
sys.path.append('/www/zelenik/')
from db_driver import pretty_json, COLORS, NEW_DISPLAYABLE

# Taken from db_driver.py
def unlink(files):
    print("Deleting %s" % [*map(str,files)])
    for file in files:
        file.unlink()

aliases_files = []
displayables_files = []

db = Path('/www/zelenik/db')

for file in db.iterdir():
    if file.is_dir():
        if file.name == 'na':
            print("Ignoring directory 'na' because it should only aliases to things in 'db'")
            continue

        aliases_file = db / file / "aliases.json"
        aliases_files.append(aliases_file)
        if not aliases_file.exists():
            unlink(displayables_files)
            raise Exception("aliases.json does not exists for %s" % file)
        with aliases_file.open() as f:
            aliases = json.loads(f.read())

        displayables = {}
        colors = list(COLORS)
        for key, value in aliases.items():
            displayables[key] = dict(NEW_DISPLAYABLE)
            displayables[key]["alias"] = value
            displayables[key]["color"] = colors.pop()

        displayables_file = db / file / "displayables.json"
        displayables_files.append(displayables_file)
        if displayables_file.exists():
            unlink(displayables_files)
            raise Exception("displayables.json already exists for %s" % file)
        with displayables_file.open('w') as f:
            f.write(pretty_json(displayables))
            print("Created displayables.json for %s", file)

print("Does db look okay? I will delete old aliases.json if yes or new displayables.json if no. (yes/No)")
yes_no = input()
if yes_no.lower() == "yes":
    unlink(aliases_files)
else: 
    unlink(displayables_files)


