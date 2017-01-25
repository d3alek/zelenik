from pathlib import Path
from datetime import date
from zipfile import ZipFile
import json
import json_delta
from datetime import datetime

def info(method, message):
    print("! db_driver/%s: %s" % (method, message))

class DatabaseDriver:
    def __init__(self, directory="db"):
        self.directory = Path(directory)
    
    def update(self, thing, state, value):
        if not type(value) is dict:
            info("update", "Called with a non-dict value - %s %s %s. Raising exception" % (thing, state, value))
            raise Exception("Expected value to be dict, got %s instead" % type(value))
        if value.get('state'):
            info("update", "Called with wrongly formatted value as 'state' object is not expected at top level, going to be added here - %s %s %s. Raising exception" % (thing, state, value))
            raise Exception('"state" object is not expected at top level, going to be added here. Got %s' % value)
        
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            thing_directory.mkdir()
            info("update", "Created new state directory for %s" % thing)

        state_path = thing_directory / state
        state_file = state_path.with_suffix(".json")

        if state_file.exists():
            with state_file.open() as f:
                previous_value = f.read()
            history_path = thing_directory / "history"
            if not history_path.is_dir():
                history_path.mkdir()
                info("update", "Created new history directory for %s" % thing)
            history_state_path = history_path / state
            history_state_file = history_state_path.with_suffix('.%d.txt' % date.today().year)

            if not history_state_file.exists():
                # if this is the beginning of a new year, put year-2 history in archive
                info("update", "First record for %s for the new year. Archiving 2 years old history" % thing)
                self.archive_history(thing, state)

            with history_state_file.open('a+') as f:
                f.write(previous_value)
                f.write('\n')

        encapsulated_value = self.encapsulate_and_timestamp(value)
        with state_file.open('w') as f:
            f.write(json.dumps(encapsulated_value))

    def encapsulate_and_timestamp(self, value):
        return {"state": value, "timestamp": datetime.utcnow().isoformat(sep=' ')}

    def archive_history(self, thing, state):
        two_years_ago = date.today().year - 2
        thing_directory = self.directory / thing
        history_path = thing_directory / "history" / state
        old_history_file = history_path.with_suffix(".%d.txt" % two_years_ago)

        if old_history_file.exists():
            archive_directory = thing_directory / "history" / "archive"
            if not archive_directory.is_dir():
                archive_directory.mkdir()
                info("archive_history", "Created new archive directory for %s" % thing)

            archive_path = archive_directory / "state"
            archive_file = archive_path.with_suffix(".%d.zip" % two_years_ago)
            with ZipFile(str(archive_file), 'w') as zf:
                zf.write(str(old_history_file), arcname=old_history_file.name)
            old_history_file.unlink() 

            info("archive_history", "Archived history from %d for %s" % (two_years_ago, thing))
        else:
            info("archive_history", "No history from %d for %s" % (two_years_ago, thing))

    def get_delta(self, thing, from_state_name, to_state_name):
        from_state, _ = self.load_state_timestamp(thing, from_state_name)
        to_state, _ = self.load_state_timestamp(thing, to_state_name)

        delta_stanza = json_delta.diff(from_state, to_state, verbose=False)

        if delta_stanza == []:
            return "{}"

        else:
            first_diff = delta_stanza[0]
            path_parts = first_diff[0]
            value = first_diff[1]
            try:
                config_location = path_parts.index('config')
            except ValueError:
                print("! get_delta: config is not in delta stanza: %s" % thing)
                print("! get_delta: FROM")
                print("! get_delta: %s" % from_state)
                print("! get_delta: TO")
                print("! get_delta: %s" % to_state)
                return '{"error":1}'
            d = value
            post_config = path_parts[config_location+1:]
            post_config.reverse()
            for path_part in post_config:
                new_d = {}
                new_d[path_part] = d     
                d = new_d

            return json.dumps(d, separators=(',', ':'))

    def load_state_timestamp(self, thing, state_name):
        thing_directory = self.directory / thing
        state_path = thing_directory / state_name
        state_file = state_path.with_suffix(".json")

        if state_file.exists():
            with state_file.open() as f:
                contents = f.read()

            deserialized = json.loads(contents)
            return deserialized['state'], deserialized['timestamp']
        else:
            print("! load_state: Tried to load state that does not exist: %s/%s" % (thing, state_name))

            return {}, {}


