from pathlib import Path
from datetime import date
from zipfile import ZipFile, ZIP_DEFLATED
import json
import json_delta
from datetime import datetime, timedelta, date
import state_processor
import re

NON_ALIASABLE = ['lawake', 'sleep', 'state', 'version', 'voltage', 'wifi', 'delete', 'delta', 'gpio', 'threshold', 'write', 'alias', 'value', 'original', 'b', 'time']

history_day_pattern = re.compile('[a-z]*.([0-9-]*).txt')

def info(method, message):
    print("  db_driver/%s: %s" % (method, message))

def error(method, message):
    print("! db_driver/%s: %s" % (method, message))

def parse_day_from_history_file(history_name):
    m = history_day_pattern.match(history_name)
    if m:
        day_string = m.group(1)
        try:
            return datetime.strptime(day_string, "%Y-%m-%d").date()
        except ValueError:
            pass

    error("parse_day_from_history_file", "Could not parse day from history file %s" % history_name)

def read_lines_single_zipped_file(file_path):
    with ZipFile(str(file_path)) as zf:
        file_name = zf.namelist()[0]
        byte_text = zf.read(file_name)
        text = byte_text.decode('utf-8')
    
    return text.splitlines()

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

    # Level 3: this class callables
    def _prepare_directory(self, directory):
        directory.mkdir()
        index = directory / "index.html"
        style = directory / "style.css"
        if not self.view.is_dir():
            self.view.mkdir()
        self.view = self.view.resolve() # need it to be absolute for symlinking to work
        index.symlink_to(self.view / "index.html")
        style.symlink_to(self.view / "style.css")

    def _append_history(self, thing, state, previous_value):
        history_path = self.directory / thing / "history"
        log_updated = []
        if not history_path.is_dir():
            history_path.mkdir()
            info("append_history", "Created new history directory for %s" % thing)
            log_updated.append('new_history_directory')
        history_state_path = history_path / state
        history_state_file = history_state_path.with_suffix('.%s.txt' % date.today().isoformat())

        if not history_state_file.exists():
            # if this is the beginning of a new day, put day-2 history in archive
            info("append_history", "First record for %s for the new day. Archiving more than 2 days old history" % thing)
            self._archive_history(thing, state)
            log_updated.append('archive')

        state_file = self._get_state_path(thing, state)

        with history_state_file.open('a+') as f:
            f.write(to_compact_json(previous_value))
            f.write('\n')
            log_updated.append('history')

        return log_updated

    def _get_state_path(self, thing, state):
        p = self.directory / thing / state
        return p.with_suffix(".json")

    def _apply_aliases(self, thing, d, aliases=None):
        if aliases is None:
            a = self._get_state_path(thing, 'aliases')
            if not a.exists():
                info('apply_aliases', 'No aliases applied because file does not exist')
                return d

            with a.open() as f:
                aliases = json.loads(f.read())

        aliased = {}
        
        for key, value in d.items():
            if type(value) is dict:
                aliased[key] = self._apply_aliases(thing, value, aliases)
            elif key in aliases.keys() and aliases[key] != "":
                aliased[key] = {
                        'value': value,
                        'alias': aliases[key]
                        }
            else:
                aliased[key] = value

        return aliased

    def _dealias(self, d):
        dealiased = {}
        
        if d.get('alias') is not None and d.get('value') is not None:
            return d['value']

        for key, value in d.items():
            if type(value) is dict:
                dealiased[key] = self._dealias(value)
            else:
                dealiased[key] = value

        return dealiased 

    def _append_new_aliasables(self, thing, value):
        aliases_file = self._get_state_path(thing, "aliases")

        if aliases_file.exists():
            aliases = self._load_state(thing, "aliases")
        else:
            aliases = {}

        keys = collect_non_dict_value_keys(value)
        keys = sorted(filter(aliasable, keys))
        for key in keys:
            if aliases.get(key) is None:
                aliases[key] = ""

        return aliases

    def _archive_history(self, thing, state):
        two_days_ago = date.today() - timedelta(days=2)
        thing_directory = self.directory / thing
        history_path = thing_directory / "history" 
        histories = [x for x in history_path.iterdir() if x.match('%s*.txt' % state)]

        for history in histories:
            day = parse_day_from_history_file(history.name)
            if day > two_days_ago:
                continue

            old_history_file = history
            with old_history_file.open() as f:
                new_archive_contents = f.read()

            archive_directory = thing_directory / "history" / "archive"
            if not archive_directory.is_dir():
                archive_directory.mkdir()
                info("archive_history", "Created new archive directory for %s" % thing)

            yearly_archive = [x for x in archive_directory.iterdir() if x.match('%s.until-%d*.zip' % (state, day.year))]
            if yearly_archive:
                yearly_archive = yearly_archive[0]
                with ZipFile(str(yearly_archive)) as zf:
                    file_name = zf.namelist()[0]
                    old_archive_contents = zf.read(file_name).decode('utf-8')
            else:
                incomplete_last_year_archive = [x for x in archive_directory.iterdir() if x.match('%s.until-%d*.zip' % (state, day.year-1))]
                if incomplete_last_year_archive:
                    incomplete_last_year_archive = incomplete_last_year_archive[0]
                    complete_last_year_archive = archive_directory / ('%s.%d.zip' % (state, day.year - 1))
                    incomplete_last_year_archive.replace(complete_last_year_archive)
                old_archive_contents = None

            archive_path = archive_directory / state
            archive_file = archive_path.with_suffix(".until-%s.zip" % day.isoformat())

            if old_archive_contents:
                contents = "%s\n%s" % (old_archive_contents, new_archive_contents)
            else:
                contents = new_archive_contents

            with ZipFile(str(archive_file), 'w', ZIP_DEFLATED) as zf:
                arcname = '%s.until-%s.txt' % (state, day.isoformat())
                zf.writestr(arcname, contents)

            old_history_file.unlink() 
            if yearly_archive:
                yearly_archive.unlink()

            info("archive_history", "Archived history from %s for %s" % (day, thing))
        else:
            info("archive_history", "No history for %s older than %s" % (thing, two_days_ago))

    def _load_state(self, thing, state_name):
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

    # Level 2: mqtt_operator callables

    def update_reported(self, thing, value):
        validate_input(thing, "reported", value)
        if value.get('state') and not isinstance(value.get('state'), str): # there is a string state attribute that can get confused with a top level state object
            raise Exception('"state" object is not expected at top level, going to be added here. Got %s' % value)
        log_updated = []
        
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            self._prepare_directory(thing_directory)
            info("update_reported", "Created new thing directory for %s" % thing)
            log_updated.append('new_thing')

        state = "reported"
        state_file = self._get_state_path(thing, state)

        value = state_processor.explode(value)
        
        if state_file.exists():
            with state_file.open() as f:
                previous_value = json.loads(f.read())
            result = self._append_history(thing, state, previous_value)
            log_updated.extend(result)

        
        desired_file = self._get_state_path(thing, "desired")
        if not desired_file.exists():
            self.update_desired(thing, value.get('config', {}))
            log_updated.append('created_desired')
        
        aliases = self._append_new_aliasables(thing, value)
        self.update_aliases(thing, aliases)
        log_updated.append('updated_aliases')

        aliased_value = self._apply_aliases(thing, value, aliases = aliases)

        encapsulated_value = encapsulate_and_timestamp(aliased_value, "state")
        with state_file.open('w') as f:
            f.write(pretty_json(encapsulated_value))
            log_updated.append('state')

        graphs = [x for x in thing_directory.iterdir() if x.match('graph*.png')]
        if len(graphs) > 0:
            for graph in graphs:
                graph.unlink()
            log_updated.append('deleted_graph')

        info("update", "[%s] updated %s" % (thing, pretty_list(log_updated)))

    def get_delta(self, thing):
        from_state = self._load_state(thing, "reported")
        if from_state.get('state') is None or from_state.get('state').get('config') is None:
            error("get_delta", "Unexpected from_state format, expected to begin with state/config. %s %s" % (thing, from_state))
            return {"error":1}
        from_state = from_state['state']['config']

        to_state = self._load_state(thing, "desired")

        if to_state == {}:
            info("get_delta", "desired of %s is empty. Assuming no delta needed." % thing)
            return {}
        from_state = self._dealias(from_state) 
        to_state = self._dealias(to_state)

        compact_from = state_processor.compact(from_state)
        compact_to = state_processor.compact(to_state)
        delta_stanza = json_delta.diff(compact_from, compact_to, verbose=False)

        if delta_stanza == []:
            return {}

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

        return delta_dict

    # Level 1: gui/user callables. Thing may be aliased, thus a_thing

    def resolve_thing(self, a_thing):
        if (self.directory / a_thing).is_dir():
            return a_thing
        aliased_dir = self.directory / "na" / a_thing
        if aliased_dir.is_symlink():
            thing = aliased_dir.resolve().name
            info("resolve_thing", "Resolved thing alias %s to %s" % (a_thing, thing))
            return thing
        else:
            raise Exception("%s is neither a thing or a thing alias." % a_thing)

    def update_thing_alias(self, thing, alias):
        if type(alias) is not str or '/' in alias:
            raise Exception("Invalid alias received for thing %s: %s" % (thing, alias))

        alias_directory = self.directory / "na"
        for existing_alias in alias_directory.iterdir():
            if existing_alias.resolve().name == thing:
                existing_alias.unlink()

        actual = self.directory / thing
        symlinked = alias_directory / alias
        symlinked.symlink_to(actual.resolve())

        info("update_thing_alias", "%s aliased to %s" % (thing, alias))


    def update_desired(self, a_thing, value):
        validate_input(a_thing, "desired", value)
        if value.get('state') or value.get('config'):
            raise Exception('"state" or "config" object is not expected at top level. Got %s' % value)

        log_updated = []

        thing = self.resolve_thing(a_thing)

        thing_directory = self.directory / thing
        if not thing_directory.exists():
            raise Exception("update_desired", "Not allowed to create new directory for desired %s %s" % (thing, value))

        state = "desired"

        state_file = self._get_state_path(thing, state)

        if state_file.exists():
            with state_file.open() as f:
                previous_value = f.read()

            encapsulated_previous_value = encapsulate_and_timestamp(previous_value, 'config')
            result = self._append_history(thing, state, encapsulated_previous_value)
            log_updated.extend(result)
            
        with state_file.open('w') as f:
            # refresh aliases
            value = self._apply_aliases(thing, self._dealias(value))

            # fill default action values if needed
            value = state_processor.explode(state_processor.compact(value))
            f.write(pretty_json(value))
            log_updated.append('state')

        info("update_desired", "[%s] updated %s" % (thing, pretty_list(log_updated)))

    def update_aliases(self, a_thing, value):
        validate_input(a_thing, "aliases", value)
        if len(list(filter(aliasable, value.keys()))) != len(value.keys()): 
            error('update_aliases', "Some of the keys are not aliasable. Ignoring update. %s %s" % (a_thing, value))
            return
        if len(list(filter(lambda s: type(s) is not str, value.values()))) > 0:
            error('update_aliases', "Some of the values are not strings. Ignoring update. %s %s" % (a_thing, value))
            return

        log_updated = []
        
        thing = self.resolve_thing(a_thing)
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            raise Exception("update_aliases", "Not allowed to create new directory for aliases %s %s" % (thing, value))

        state = "aliases"

        state_file = self._get_state_path(thing, state)

        if state_file.exists():
            with state_file.open() as f:
                previous_value = json.loads(f.read())

            encapsulated_previous_value = encapsulate_and_timestamp(previous_value, 'state')
            result = self._append_history(thing, state, encapsulated_previous_value)
            log_updated.extend(result)
            
        with state_file.open('w') as f:
            f.write(pretty_json(value))
            log_updated.append('state')

        info("update_aliases", "[%s] updated %s" % (thing, pretty_list(log_updated)))

    def _load_history_for_year(self, thing, state_name, year):
        archive_path = self.directory / thing / "history"/ "archive" 
        if not archive_path.is_dir():
            info("load_history_for_year", "No history exists for %s %s for %s" % (thing, state_name, year))
            return []

        complete = archive_path / state_name
        complete = complete.with_suffix('.%s.zip')
        history = []
        if complete.exists():
            text = read_lines_single_zipped_file(complete)
            history = list(map(json.loads, text))
        else:
            incomplete = [x for x in archive_path.iterdir() if x.match('%s.until-%d*.zip' % (state_name, year))]
            if len(incomplete) > 0:
                incomplete = incomplete[0]
                text = read_lines_single_zipped_file(incomplete)
                history = list(map(json.loads, text))
            else:
                info("load_history_for_year", "No history exists for %s %s for %s" % (thing, state_name, year))

        return history 

    def _load_history_for_day(self, thing, state_name, day):
        history_path = self.directory / thing / "history"/ state_name
        history_file = history_path.with_suffix(".%s.txt" % day.isoformat())

        if history_file.exists():
            with history_file.open() as f:
                states = list(map(json.loads, f.readlines()))
        else:
            info("load_history_for_day", "No history exists for %s %s for %s" % (thing, state_name, day))
            states = []

        return states

    def load_history(self, a_thing, state_name, since_days=1):
        thing = self.resolve_thing(a_thing)

        thing_directory = self.directory / thing

        history_path = thing_directory / "history"/ state_name
        today = date.today()
        yesterday = today - timedelta(days=1)
        history = []
        history.extend(self._load_history_for_day(thing, state_name, yesterday))
        history.extend(self._load_history_for_day(thing, state_name, today))

        if since_days > 1:
            history.extend(self._load_history_for_year(thing, state_name, today.year))
            days_since_start_of_year = today.month * 29 + today.day # approximate, understatement
            if since_days > days_since_start_of_year:
                history.extend(self._load_history_for_year(thing, state_name, today.year - 1))

        state = self._load_state(thing, state_name)
        history.append(state)
        since_day = datetime.utcnow() - timedelta(days=since_days)
        filtered_history = list(filter(lambda s: parse_isoformat(s['timestamp_utc']) > since_day, history))
        return filtered_history


