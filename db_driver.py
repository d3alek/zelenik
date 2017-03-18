from pathlib import Path
from datetime import date
from zipfile import ZipFile
import json
import json_delta
from datetime import datetime, timedelta
import state_processor

NON_ALIASABLE = ['lawake', 'sleep', 'state', 'version', 'voltage', 'wifi', 'delete', 'delta', 'gpio', 'threshold', 'write', 'alias', 'value']
def aliasable(s):
    b = s not in NON_ALIASABLE
    return b and not s.startswith('A|')

# parse iso format datetime with sep=' '
def parse_isoformat(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")

def pretty_json(d):
    return json.dumps(d, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False)

def to_compact_json(s):
    return json.dumps(s, separators=(',', ':'))

def pretty_list(l):
    return ', '.join(map(str, l))

def info(method, message):
    print("  db_driver/%s: %s" % (method, message))

def error(method, message):
    print("! db_driver/%s: %s" % (method, message))

def validate_input(thing, state, value):
    if not type(value) is dict:
        error("update", "Called with a non-dict value - %s %s %s. Raising exception" % (thing, state, value))
        raise Exception("Expected value to be dict, got %s instead" % type(value))

def encapsulate_and_timestamp(value, parent_name):
    return {parent_name: value, "timestamp_utc": datetime.utcnow().isoformat(sep=' ')}

def collect_non_dict_value_keys(d):
    collected = []
    for key, value in d.items():
        if type(value) is dict:
            collected.extend(collect_non_dict_value_keys(value))
        else:
            collected.append(key) 

    return collected

class DatabaseDriver:
    def __init__(self, working_directory="", directory="db", view='view'):
        self.directory = Path(working_directory) / directory
        self.view = (Path(working_directory) / view)

    def prepare_directory(self, directory):
        directory.mkdir()
        index = directory / "index.html"
        style = directory / "style.css"
        if not self.view.is_dir():
            self.view.mkdir()
        self.view = self.view.resolve() # need it to be absolute for symlinking to work
        index.symlink_to(self.view / "index.html")
        style.symlink_to(self.view / "style.css")

    def append_history(self, thing, state, previous_value):
        history_path = self.directory / thing / "history"
        log_updated = []
        if not history_path.is_dir():
            history_path.mkdir()
            info("append_history", "Created new history directory for %s" % thing)
            log_updated.append('new_history_directory')
        history_state_path = history_path / state
        history_state_file = history_state_path.with_suffix('.%d.txt' % date.today().year)

        if not history_state_file.exists():
            # if this is the beginning of a new year, put year-2 history in archive
            info("update", "First record for %s for the new year. Archiving 2 years old history" % thing)
            self.archive_history(thing, state)
            log_updated.append('archive')

        state_file = self.get_state_path(thing, state)

        with history_state_file.open('a+') as f:
            f.write(to_compact_json(previous_value))
            f.write('\n')
            log_updated.append('history')

        return log_updated

    def get_state_path(self, thing, state):
        p = self.directory / thing / state
        return p.with_suffix(".json")

    def apply_aliases(self, thing, d, aliases=None):
        if aliases is None:
            a = self.get_state_path(thing, 'aliases')
            with a.open() as f:
                aliases = json.loads(f.read())

        aliased = {}
        
        for key, value in d.items():
            if type(value) is dict:
                aliased[key] = self.apply_aliases(thing, value, aliases)
            elif key in aliases.keys() and aliases[key] != "":
                aliased[key] = {
                        'value': value,
                        'alias': aliases[key]
                        }
            else:
                aliased[key] = value

        return aliased

    def dealias(self, d):
        dealiased = {}
        
        if d.get('alias') is not None and d.get('value') is not None:
            return d['value']

        for key, value in d.items():
            if type(value) is dict:
                dealiased[key] = self.dealias(value)
            else:
                dealiased[key] = value

        return dealiased 

    def update_reported(self, thing, value):
        validate_input(thing, "reported", value)
        if value.get('state') and not isinstance(value.get('state'), str): # there is a string state attribute that can get confused with a top level state object
            raise Exception('"state" object is not expected at top level, going to be added here. Got %s' % value)
        log_updated = []
        
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            self.prepare_directory(thing_directory)
            info("update_reported", "Created new thing directory for %s" % thing)
            log_updated.append('new_thing')

        state = "reported"
        state_file = self.get_state_path(thing, state)

        value = state_processor.explode(value)
        
        if state_file.exists():
            with state_file.open() as f:
                previous_value = json.loads(f.read())
            result = self.append_history(thing, state, previous_value)
            log_updated.extend(result)

        
        desired_file = self.get_state_path(thing, "desired")
        if not desired_file.exists():
            self.update_desired(thing, value.get('config', {}))
            log_updated.append('created_desired')
        
        aliases = self.append_new_aliasables(thing, value)
        self.update_aliases(thing, aliases)
        log_updated.append('updated_aliases')

        aliased_value = self.apply_aliases(thing, value, aliases = aliases)

        encapsulated_value = encapsulate_and_timestamp(aliased_value, "state")
        with state_file.open('w') as f:
            f.write(pretty_json(encapsulated_value))
            log_updated.append('state')

        graph = thing_directory / "graph.png"
        if graph.exists():
            graph.unlink()
            log_updated.append('deleted_graph')

        info("update", "[%s] updated %s" % (thing, pretty_list(log_updated)))

    def append_new_aliasables(self, thing, value):
        aliases_file = self.get_state_path(thing, "aliases")

        if aliases_file.exists():
            aliases = self.load_state(thing, "aliases")
        else:
            aliases = {}

        keys = collect_non_dict_value_keys(value)
        keys = sorted(filter(aliasable, keys))
        for key in keys:
            if aliases.get(key) is None:
                aliases[key] = ""

        return aliases

    def update_desired(self, thing, value):
        validate_input(thing, "desired", value)
        if value.get('state') or value.get('config'):
            raise Exception('"state" or "config" object is not expected at top level. Got %s' % value)

        log_updated = []
        
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            raise Exception("update_desired", "Not allowed to create new directory for desired %s %s" % (thing, value))

        state = "desired"

        state_file = self.get_state_path(thing, state)

        if state_file.exists():
            with state_file.open() as f:
                previous_value = f.read()

            encapsulated_previous_value = encapsulate_and_timestamp(previous_value, 'config')
            result = self.append_history(thing, state, encapsulated_previous_value)
            log_updated.extend(result)
            
        with state_file.open('w') as f:
            # refresh aliases
            value = self.apply_aliases(thing, self.dealias(value))
            # fill default action values if needed
            value = state_processor.explode(state_processor.compact(value))
            f.write(pretty_json(value))
            log_updated.append('state')

        info("update_desired", "[%s] updated %s" % (thing, pretty_list(log_updated)))

    def update_aliases(self, thing, value):
        validate_input(thing, "aliases", value)
        if len(list(filter(aliasable, value.keys()))) != len(value.keys()): 
            error('update_aliases', "Some of the keys are not aliasable. Ignoring update. %s %s" % (thing, value))
            return
        if len(list(filter(lambda s: type(s) is not str, value.values()))) > 0:
            error('update_aliases', "Some of the values are not strings. Ignoring update. %s %s" % (thing, value))
            return

        log_updated = []
        
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            raise Exception("update_aliases", "Not allowed to create new directory for aliases %s %s" % (thing, value))

        state = "aliases"

        state_file = self.get_state_path(thing, state)

        if state_file.exists():
            with state_file.open() as f:
                previous_value = json.loads(f.read())

            encapsulated_previous_value = encapsulate_and_timestamp(previous_value, 'state')
            result = self.append_history(thing, state, encapsulated_previous_value)
            log_updated.extend(result)
            
        with state_file.open('w') as f:
            f.write(pretty_json(value))
            log_updated.append('state')

        info("update_aliases", "[%s] updated %s" % (thing, pretty_list(log_updated)))


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

            archive_path = archive_directory / state
            archive_file = archive_path.with_suffix(".%d.zip" % two_years_ago)
            with ZipFile(str(archive_file), 'w') as zf:
                zf.write(str(old_history_file), arcname=old_history_file.name)
            old_history_file.unlink() 

            info("archive_history", "Archived history from %d for %s" % (two_years_ago, thing))
        else:
            info("archive_history", "No history from %d for %s" % (two_years_ago, thing))

    def get_delta(self, thing):
        from_state = self.load_state(thing, "reported")
        if from_state.get('state') is None or from_state.get('state').get('config') is None:
            error("get_delta", "Unexpected from_state format, expected to begin with state/config. %s %s" % (thing, from_state))
            return '{"error":1}'
        from_state = from_state['state']['config']

        to_state = self.load_state(thing, "desired")

        if to_state == {}:
            info("get_delta", "desired of %s is empty. Assuming no delta needed." % thing)
            return "{}"
        from_state = self.dealias(from_state) 
        to_state = self.dealias(to_state)

        compact_from = state_processor.compact(from_state)
        compact_to = state_processor.compact(to_state)
        delta_stanza = json_delta.diff(compact_from, compact_to, verbose=False)

        print(from_state, to_state, delta_stanza)
        if delta_stanza == []:
            return "{}"

        delta_dict = {}
        for diff in delta_stanza:
            path_parts = diff[0]
            if len(diff) == 1:
                #TODO happens when something existing in from is not in to - then only the path to the thing in from is given, signaling delete
                info("get_delta", "No value specified in diff, seems like field present in from is missing in to - skipping. %s %s" % (thing, diff))
                continue
            value = diff[1]
            d = value
            post_config = path_parts
            post_config.reverse()
            for path_part in post_config:
                new_d = {}
                new_d[path_part] = d     
                d = new_d
            delta_dict.update(d)

        return json.dumps(delta_dict, separators=(',', ':'))

    def load_state(self, thing, state_name):
        thing_directory = self.directory / thing
        state_path = thing_directory / state_name
        state_file = state_path.with_suffix(".json")

        if state_file.exists():
            with state_file.open() as f:
                contents = f.read()

            deserialized = json.loads(contents)
            return deserialized
        else:
            info("load_state", "Tried to load state that does not exist: %s/%s" % (thing, state_name))

            return {}

    def load_history(self, thing, state_name, since_days=1):
        thing_directory = self.directory / thing

        history_path = thing_directory / "history"/ state_name
        #TODO handle multiple years by loading year-1 as well
        today = datetime.utcnow()
        history_file = history_path.with_suffix(".%d.txt" % today.year)
        if history_file.exists():
            with history_file.open() as f:
                states = list(map(json.loads, f.readlines()))
        else:
            info("load_history", "No history exists for %s %s" % (thing, state_name))
            states = []

        state = self.load_state(thing, state_name)
        states.append(state)
        since_day = today - timedelta(days=since_days)
        filtered_states = list(filter(lambda s: parse_isoformat(s['timestamp_utc']) > since_day, states))
        return filtered_states


