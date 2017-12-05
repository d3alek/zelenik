from pathlib import Path
import sys
root_path = Path(__file__).parent.parent
sys.path.append(str(root_path.absolute()))

from datetime import date
from zipfile import ZipFile, ZIP_DEFLATED
import json
import json_delta
from datetime import datetime, timedelta, date
import state_processor
from state_processor import parse_isoformat
import re

from logger import Logger
logger = Logger("db_driver")

NON_ALIASABLE = ['lawake', 'sleep', 'state', 'version', 'voltage', 'wifi', 'delete', 'delta', 'gpio', 'threshold', 'write', 'alias', 'value', 'original', 'b', 'time', 'actions']

history_day_pattern = re.compile('[a-z]*.([0-9-]*).txt')

SHOULD_ENCHANT_FLAG = '.should-enchant.flag'

def safe_json_loads(s):
    try:
        return json.loads(s)
    except json.decoder.JSONDecodeError:
        logger.of('safe_json_loads').error("Could not parse %s" % s, traceback = True) 
        return None

def change_action_diff_format(path_parts, value, compact_to):
    # Go from ['actions', 0], 'I2C-8|4|H|10|2'
    # and to_compact {"actions": {'I2C-8|4|H|10|2', 'I2C-8|4|H|10|3'}}
    # to ['actions'], ['I2C-8|4|H|10|2', 'I2C-8|4|H|10|3']
    if len(path_parts) == 2 and path_parts[0] == 'actions':
        action_list = list(compact_to['actions'])
        path_parts.pop() # remove changed_index
        return ['actions'], action_list

    return path_parts, value 

def parse_day_from_history_file(history_name):
    m = history_day_pattern.match(history_name)
    if m:
        day_string = m.group(1)
        try:
            return datetime.strptime(day_string, "%Y-%m-%d").date()
        except ValueError:
            pass

    log = logger.of("parse_day_from_history_file")
    log.error("Could not parse day from history file %s. Using two days ago." % history_name)
    return date.today() - timedelta(days=2)

def read_lines_single_zipped_file(file_path):
    with ZipFile(str(file_path)) as zf:
        file_name = zf.namelist()[0]
        byte_text = zf.read(file_name)
        text = byte_text.decode('utf-8')
    
    return text.splitlines()

def is_displayable(s):
    b = s not in NON_ALIASABLE
    return b and not s.startswith('A|') and (not ':' in s)

def pretty_json(d):
    return json.dumps(d, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False)

def to_compact_json(s):
    return json.dumps(s, separators=(',', ':'))

def pretty_list(l):
    return ', '.join(map(str, l))

def validate_input(thing, state, value):
    log = logger.of('validate_input')
    if state == 'enchanter':
        if not type(value) is list:
            raise Exception("Expected value to be list, got %s instead" % type(value))
    elif not type(value) is dict:
        log.error("Called with a non-dict value - %s %s %s. Raising exception" % (thing, state, value))
        raise Exception("Expected value to be dict, got %s instead" % type(value))

def timestamp(time):
    time = time.replace(microsecond=0)
    return time.isoformat(sep=' ')

def encapsulate_and_timestamp(value, parent_name, time=datetime.utcnow()):
    return {parent_name: value, "timestamp_utc": timestamp(time)}

def flat_map(d, field, default="", strict=False):
    filtered = {}
    for key, value in d.items():
        if type(value) is dict:
            if strict and field not in value:
                continue
            filtered[key] = value.get(field, default)

    return filtered

def prepare_test_directory(directory_path):
    db_directory = directory_path / "db"
    db_directory.mkdir()

    view_directory = directory_path / "view"
    view_location = view_directory.name
    view_directory.mkdir()
    index = view_directory  / "index.html"
    index.touch()
    style = view_directory / "style.html"
    style.touch()

class DatabaseDriver:
    def __init__(self, working_directory="", directory="db", view='view'):
        self.directory = Path(working_directory) / directory
        self.view = (Path(working_directory) / view)

    # Level 3: this class callables
    def _prepare_directory(self, directory):
        directory.mkdir()
        directory.chmod(0o774)
        index = directory / "index.html"
        view = directory / "view"
        if not self.view.is_dir():
            self.view.mkdir()
            self.view.chmod(0o774)
        self.view = self.view.resolve() # need it to be absolute for symlinking to work
        index.symlink_to(self.view / "index.html")
        view.symlink_to(self.view)

    def _append_history(self, thing, state, previous_value):
        log = logger.of('_append_history')
        history_path = self.directory / thing / "history"
        log_updated = []
        if not history_path.is_dir():
            history_path.mkdir()
            history_path.chmod(0o774)
            log.info("Created new history directory for %s" % thing)
            log_updated.append('new_history_directory')
        history_state_path = history_path / state
        history_state_file = history_state_path.with_suffix('.%s.txt' % date.today().isoformat())

        if not history_state_file.exists():
            # if this is the beginning of a new day, put day-2 history in archive
            log.info("First record for %s for the new day. Archiving more than 2 days old history" % thing)
            self._archive_history(thing, state)
            log_updated.append('archive')

        state_file = self._get_state_path(thing, state)

        with history_state_file.open('a+', encoding='utf-8') as f:
            f.write(to_compact_json(previous_value))
            f.write('\n')
            log_updated.append('history')

        return log_updated

    def _get_state_path(self, thing, state):
        p = self.directory / thing / state
        return p.with_suffix(".json")

    def _get_should_enchant_flag_path(self, thing):
        return self.directory / thing / SHOULD_ENCHANT_FLAG 

    def _apply_aliases(self, thing, d, aliases=None):
        log = logger.of('_apply_aliases')
        if aliases is None:
            a = self._get_state_path(thing, 'displayables')
            if not a.exists():
                log.info('No aliases applied because file does not exist')
                return d

            with a.open(encoding='utf-8') as f:
                displayables = json.loads(f.read())
                aliases = flat_map(displayables, 'alias')

        aliased = {}
        
        for key, value in d.items():
            alias = aliases.get(key, "")
            if type(value) is dict:
                if 'value' in value and alias != "":
                    # something already exploded it, probably state_processor, so just append alias
                    aliased[key] = value
                    aliased[key]['alias'] = alias
                else:
                    aliased[key] = self._apply_aliases(thing, value, aliases)
            elif key in aliases.keys() and alias != "":
                aliased[key] = {
                        'value': value,
                        'alias': alias
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

    def _archive_history(self, thing, state):
        log = logger.of('_archive_history')
        year = date.today().year
        two_days_ago = date.today() - timedelta(days=2)
        thing_directory = self.directory / thing
        history_path = thing_directory / "history" 
        histories = [x for x in history_path.iterdir() if x.match('%s*.txt' % state)]

        for history in histories:
            day = parse_day_from_history_file(history.name)
            if day > two_days_ago:
                continue

            old_history_file = history
            with old_history_file.open(encoding='utf-8') as f:
                lines = f.readlines()

            error_free_contents = "\n".join(map(to_compact_json, [x for x in map(safe_json_loads, lines) if x is not None]))

            archive_directory = thing_directory / "history" / "archive"
            if not archive_directory.is_dir():
                archive_directory.mkdir()
                archive_directory.chmod(0o774)
                log.info("Created new archive directory for %s" % thing)

            year_directory = archive_directory / str(year)

            if not year_directory.is_dir():
                year_directory.mkdir()
                year_directory.chmod(0o774)
                log.info("Created new archive directory for %s year %s" % (thing, year))

            archive_path = year_directory / state
            archive_file = archive_path.with_suffix(".%s.zip" % day.isoformat())

            with ZipFile(str(archive_file), 'w', ZIP_DEFLATED) as zf:
                arcname = '%s.%s.txt' % (state, day.isoformat())
                zf.writestr(arcname, error_free_contents)

            old_history_file.unlink() 

            log.info("Archived history from %s for %s" % (day, thing))
        else:
            log.info("No history for %s older than %s" % (thing, two_days_ago))

    def update(self, state, thing, value):
        if state == 'reported':
            self._update_reported(thing, value)
        elif state == 'desired':
            self._update_desired(thing, value)
        elif state == 'thing-alias':
            self._update_thing_alias(thing, value)
        elif state == 'enchanter':
            self._update_enchanter(thing, value)
        elif state == 'displayables':
            self._update_displayables(thing, value)
        elif state == 'plot-background':
            self._update_plot_background(thing, value)
        else:
            logger.of('update').error('Unknown update state %s' % state)
            raise Exception('Unknown update state %s' % state)

        with (self.directory / 'last-modified.txt').open('w', encoding='utf-8') as f:
            f.write(timestamp(datetime.utcnow()))

    # Level 2: mqtt_operator callables

    def _update_reported(self, thing, value, time=datetime.utcnow()):
        log = logger.of('update_reported')
        validate_input(thing, "reported", value)
        if value.get('state') and not isinstance(value.get('state'), str): # there is a string state attribute that can get confused with a top level state object
            raise Exception('"state" object is not expected at top level, going to be added here. Got %s' % value)
        log_updated = []
        
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            self._prepare_directory(thing_directory)
            log.info("Created new thing directory for %s" % thing)
            log_updated.append('new_thing')

        state = "reported"
        state_file = self._get_state_path(thing, state)

        if state_file.exists():
            with state_file.open(encoding='utf-8') as f:
                previous_value = json.loads(f.read())
            result = self._append_history(thing, state, previous_value)
            log_updated.extend(result)
            previous_state = previous_value.get('state', {})
            previous_timestamp = previous_value.get('timestamp_utc', None)
        else:
            previous_state = {}
            previous_timestamp = None

        value = state_processor.explode(value)
        
        desired_file = self._get_state_path(thing, "desired")
        if not desired_file.exists():
            self._update_desired(thing, value.get('config', {}))
            log_updated.append('created_desired')
        
        encapsulated_value = encapsulate_and_timestamp(value, "state", time=time)
        with state_file.open('w', encoding='utf-8') as f:
            f.write(pretty_json(encapsulated_value))
            log_updated.append('state')

        should_enchant_flag = self._get_should_enchant_flag_path(thing)

        should_enchant_flag.touch()

        graphs = [x for x in thing_directory.iterdir() if x.match('graph*.png')]
        if len(graphs) > 0:
            for graph in graphs:
                graph.unlink()
            log_updated.append('deleted_graph')

        log.info("[%s] updated %s" % (thing, pretty_list(log_updated)))

    def get_delta(self, thing):
        log = logger.of('get_delta')
        from_state = self.load_state(thing, "reported")
        if from_state.get('state') is None or from_state.get('state').get('config') is None:
            log.error("Unexpected from_state format, expected to begin with state/config. %s %s" % (thing, from_state))
            return {"error":1}
        from_state = from_state['state']['config']

        to_state = self.load_state(thing, "desired")

        if to_state == {}:
            log.info("desired of %s is empty. Assuming no delta needed." % thing)
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
                log.info("No value specified in diff, seems like field present in from is missing in to - skipping. %s %s" % (thing, diff))
                continue
            value = diff[1]
            path_parts, value = change_action_diff_format(path_parts, value, compact_to)
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

    def load_state(self, thing, state_name):
        thing_directory = self.directory / thing
        state_path = thing_directory / state_name
        state_file = state_path.with_suffix(".json")

        if state_file.exists():
            with state_file.open(encoding='utf-8') as f:
                contents = f.read()

            deserialized = safe_json_loads(contents)
            if deserialized is None:
                return {}
            return deserialized
        else:
            log = logger.of('load_state')
            log.info("Tried to load state that does not exist: %s/%s" % (thing, state_name))

            return {}

    def alias_thing(self, thing):
        log = logger.of('alias_thing')
        alias = thing
        alias_directory = self.directory / 'na'
        for existing_alias in alias_directory.iterdir():
            if existing_alias.resolve().name == thing:
                alias = existing_alias.name
                break

        return alias

    def resolve_thing(self, a_thing):
        log = logger.of('resolve_thing')
        if (self.directory / a_thing).is_dir():
            return a_thing
        aliased_dir = self.directory / "na" / a_thing
        if aliased_dir.is_symlink():
            thing = aliased_dir.resolve().name
            log.info("Resolved thing alias %s to %s" % (a_thing, thing))
            return thing
        else:
            log.warning("%s is neither a thing or a thing alias." % a_thing)
            return None


    def _update_thing_alias(self, thing, alias):
        if type(alias) is not str or '/' in alias:
            raise Exception("Invalid alias received for thing %s: %s" % (thing, alias))

        alias_directory = self.directory / "na"
        for existing_alias in alias_directory.iterdir():
            if existing_alias.resolve().name == thing:
                existing_alias.unlink()

        actual = self.directory / thing
        symlinked = alias_directory / alias
        symlinked.symlink_to(actual.resolve())
        log = logger.of('update_thing_alias')
        log.info("%s aliased to %s" % (thing, alias))

    def _update_enchanter(self, a_thing, value):
        log = logger.of('update_enchanter')

        validate_input(a_thing, "enchanter", value)
        log_updated = []
        thing = self.resolve_thing(a_thing)

        thing_directory = self.directory / thing
        if not thing_directory.exists():
            raise Exception("update_enchanter", "Not allowed to create new directory for enchanter %s %s" % (thing, value))

        state = "enchanter"

        state_file = self._get_state_path(thing, state)

        if state_file.exists():
            with state_file.open(encoding='utf-8') as f:
                previous_value = json.loads(f.read())

            encapsulated_previous_value = encapsulate_and_timestamp(previous_value, 'state')
            result = self._append_history(thing, state, encapsulated_previous_value)
            log_updated.extend(result)
            
        with state_file.open('w', encoding='utf-8') as f:
            f.write(pretty_json(value))
            log_updated.append('state')

        log.info("[%s] updated %s" % (thing, pretty_list(log_updated)))



    def _update_desired(self, a_thing, value):
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
            with state_file.open(encoding='utf-8') as f:
                previous_value = f.read()

            encapsulated_previous_value = encapsulate_and_timestamp(previous_value, 'config')
            result = self._append_history(thing, state, encapsulated_previous_value)
            log_updated.extend(result)
            
        with state_file.open('w', encoding='utf-8') as f:
            # refresh aliases
            value = self._apply_aliases(thing, self._dealias(value))

            # fill default action values if needed
            value = state_processor.explode(state_processor.compact(value))
            f.write(pretty_json(value))
            log_updated.append('state')

        log = logger.of('update_desired')
        log.info("[%s] updated %s" % (thing, pretty_list(log_updated)))

    def _update_displayables(self, a_thing, value):
        log = logger.of('update_displayables')
        validate_input(a_thing, "displayables", value)
        if len(list(filter(is_displayable, value.keys()))) != len(value.keys()): 
            log.error("Some of the keys are not displayable. Ignoring update. %s %s" % (a_thing, value))
            return

        log_updated = []
        
        thing = self.resolve_thing(a_thing)
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            raise Exception("update_displayables", "Not allowed to create new directory for displayables %s %s" % (thing, value))

        state = "displayables"

        state_file = self._get_state_path(thing, state)

        if state_file.exists():
            with state_file.open(encoding='utf-8') as f:
                previous_value = json.loads(f.read())

            encapsulated_previous_value = encapsulate_and_timestamp(previous_value, 'state')
            result = self._append_history(thing, state, encapsulated_previous_value)
            log_updated.extend(result)
            
        with state_file.open('w', encoding='utf-8') as f:
            f.write(pretty_json(value))
            log_updated.append('state')

        log.info("[%s] updated %s" % (thing, pretty_list(log_updated)))

    def _load_archive_for_day(self, thing, state_name, day):
        log = logger.of('load_archive_for_day')
        year = day.year
        archive_path = self.directory / thing / "history"/ "archive" / str(year) / state_name
        archive_file = archive_path.with_suffix(".%s.zip" % day.isoformat())

        if archive_file.exists():
            text = read_lines_single_zipped_file(archive_file)
            states = list(map(json.loads, text))
        else:
            states = []

        return states

    def _load_history_for_day(self, thing, state_name, day):
        history_path = self.directory / thing / "history"/ state_name
        history_file = history_path.with_suffix(".%s.txt" % day.isoformat())

        if history_file.exists():
            with history_file.open(encoding='utf-8') as f:
                states = [x for x in map(safe_json_loads, f.readlines()) if x is not None]
        else:
            log = logger.of("load_history_for_day")
            log.info("No history exists for %s %s for %s" % (thing, state_name, day))
            states = []

        return states

    def load_history(self, a_thing, state_name, since_days=1):
        thing = self.resolve_thing(a_thing)

        thing_directory = self.directory / thing

        history_path = thing_directory / "history"/ state_name
        today = date.today()
        yesterday = today - timedelta(days=1)
        history = []

        for since_day in reversed(range(2, since_days+1)):
            day = today - timedelta(days=since_day)
            history.extend(self._load_archive_for_day(thing, state_name, day))

        history.extend(self._load_history_for_day(thing, state_name, yesterday))
        history.extend(self._load_history_for_day(thing, state_name, today))

        state = self.load_state(thing, state_name)
        if state:
            history.append(state)

        since_datetime = datetime.utcnow() - timedelta(days=since_days)
        filtered_history = list(filter(lambda s: parse_isoformat(s['timestamp_utc']) > since_datetime, history))
        return filtered_history 

    def _update_plot_background(self, a_thing, svg_bytes):
        thing = self.resolve_thing(a_thing)
        plot_path = self.directory / thing / 'plot.png'
        with plot_path.open('wb') as f:
            f.write(svg_bytes)

    def get_thing_list(self):
        return [thing_path.name for thing_path in self.directory.iterdir() if thing_path.is_dir() and thing_path.name not in ('na', 'stado')]

    def last_modified(self):
        with (self.directory / 'last-modified.txt').open(encoding='utf-8') as f:
            modified = parse_isoformat(f.read())
        return modified
