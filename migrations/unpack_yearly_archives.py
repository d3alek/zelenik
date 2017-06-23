#!/www/zelenik/venv/bin/python

from pathlib import Path
import json

import sys
sys.path.append('/www/zelenik/')

from db_driver import read_lines_single_zipped_file, parse_isoformat, to_compact_json

from zipfile import ZipFile, ZIP_DEFLATED

# Taken from db_driver.py
def unlink(files):
    print("Deleting %s" % [*map(str,files)])
    for file in files:
        file.unlink()

old_archives = []
new_archives = []

db = Path('/www/zelenik/db')

def safe_loads(t):
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        print("Ignoring %s because of parsing error" % t)
        return None


for file in db.iterdir():
    if file.is_dir():
        if file.name == 'na':
            print("Ignoring directory 'na' because it should only aliases to things in 'db'")
            continue

        archive_path = db / file / "history" / "archive" 
        if not archive_path.is_dir():
            print("Ignoring directory %s because it does not contain history/archive" % file)
            continue

        until_archives = [x for x in archive_path.iterdir() if 'until-' in x.name]

        for old_archive in until_archives:
            state_name = old_archive.name.split('.until-')[0]
            lines = read_lines_single_zipped_file(old_archive) 
            states = map(safe_loads, lines) 
            states_per_date = {}
            for state in states:
                if state is None:
                    continue
                day = parse_isoformat(state['timestamp_utc']).date()
                if day in states_per_date:
                    states_per_date[day].append(state)
                else:
                    states_per_date[day] = [state]

            for day, states in states_per_date.items():
                year = day.year
                contents = "\n".join(map(to_compact_json, states))
                year_path = archive_path / str(year)
                p = year_path / state_name
                p = p.with_suffix('.%s.zip' % day.isoformat())

                if not year_path.is_dir():
                    year_path.mkdir()
                    year_path.chmod(0o774)
                    print("Created new archive directory for %s year %s" % (file.name, year))

                with ZipFile(str(p), 'w', ZIP_DEFLATED) as zf:
                    arcname = '%s.%s.txt' % (state_name, day.isoformat())
                    zf.writestr(arcname, contents)
                new_archives.append(p)

            print("Unpacked %s" % old_archive)

        old_archives.append(until_archives)

print("Does db look okay? I will delete old until archives if yes or new daily archives if no. (yes/No)")
yes_no = input()
if yes_no.lower() == "yes":
    unlink(old_archives)
else: 
    unlink(new_archives)


