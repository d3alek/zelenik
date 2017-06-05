from pathlib import Path
from datetime import date
from zipfile import ZipFile, ZIP_DEFLATED
import json
import json_delta
from datetime import datetime, timedelta, date
import state_processor
from state_processor import parse_isoformat
import re
from matplotlib import colors

NON_ALIASABLE = ['lawake', 'sleep', 'state', 'version', 'voltage', 'wifi', 'delete', 'delta', 'gpio', 'threshold', 'write', 'alias', 'value', 'original', 'b', 'time', 'actions']

history_day_pattern = re.compile('[a-z]*.([0-9-]*).txt')

NEW_DISPLAYABLE = {"alias":"", "color": "green", "position":"0,0","type":"number","plot":"yes","graph":"yes"}

FIRST_COLORS = ['green', 'red', 'blue', 'purple', 'brown', 'orange']

def set_subtract(subtract_from, to_subtract):
    return [item for item in subtract_from if item not in to_subtract]

COLORS = list(reversed(FIRST_COLORS + set_subtract(colors.cnames.keys(), FIRST_COLORS))) # revsersing because the intended use is to instantiate a new list and pop out

def info(method, message):
    print("  db_driver/%s: %s" % (method, message))

def error(method, message):
    print("! db_driver/%s: %s" % (method, message))

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

    error("parse_day_from_history_file", "Could not parse day from history file %s. Using two days ago." % history_name)
    return date.today() - timedelta(days=2)

def read_lines_single_zipped_file(file_path):
    with ZipFile(str(file_path)) as zf:
        file_name = zf.namelist()[0]
        byte_text = zf.read(file_name)
        text = byte_text.decode('utf-8')
    
    return text.splitlines()

def is_displayable(s):
    b = s not in NON_ALIASABLE
    return b and not s.startswith('A|')

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

def timestamp(time):
    time = time.replace(microsecond=0)
    return time.isoformat(sep=' ')

def encapsulate_and_timestamp(value, parent_name):
    return {parent_name: value, "timestamp_utc": timestamp(datetime.utcnow())}

def collect_non_dict_value_keys(d):
    collected = []
    for key, value in d.items():
        if type(value) is dict:
            collected.extend(collect_non_dict_value_keys(value))
        else:
            collected.append(key) 

    return collected

def flat_map(d, field):
    filtered = {}
    for key, value in d.items():
        if type(value) is dict:
            filtered[key] = value.get(field, "")

    return filtered

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
        history_path = self.directory / thing / "history"
        log_updated = []
        if not history_path.is_dir():
            history_path.mkdir()
            history_path.chmod(0o774)
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
            a = self._get_state_path(thing, 'displayables')
            if not a.exists():
                info('apply_aliases', 'No aliases applied because file does not exist')
                return d

            with a.open() as f:
                displayables = json.loads(f.read())
                aliases = flat_map(displayables, 'alias')

        aliased = {}
        
        for key, value in d.items():
            alias = aliases.get(key, "")
            if type(value) is dict:
                if value.get('value', None) is not None and alias != "":
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

    def _get_new_displayables(self, value, previous_displayables):
        new_displayables = {}
        keys = collect_non_dict_value_keys(value)
        keys = sorted(filter(is_displayable, keys))
        previous_keys = previous_displayables.keys()
        used_colors = flat_map(previous_displayables, "color").values()
        unused_colors = set_subtract(COLORS, used_colors)
        for key in keys:
            if key not in previous_keys:
                if not unused_colors:
                    error("get_new_displayables", "No more unused colors. Starting to repeat")
                    unused_colors = list(COLORS)

                new_displayables[key] = dict(NEW_DISPLAYABLE)
                if key == 'A0':
                    new_displayables[key]['color'] = 'yellow'
                    new_displayables[key]['type'] = 'percent'
                    new_displayables[key]['alias'] = 'светлина'
                else:
                    new_displayables[key]['color'] = unused_colors.pop()

                if key.startswith('OW-'):
                    new_displayables[key]['type'] = 'temp'
                elif key.startswith('I2C-'):
                    new_displayables[key]['type'] = 'percent'
                    new_displayables[key]['alias'] = key.split('-')[1]
                elif key in ['4', '5', '13']:
                    new_displayables[key]['type'] = 'switch'


        return new_displayables

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
                archive_directory.chmod(0o774)
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
                old_archive_contents = ""

            archive_path = archive_directory / state
            archive_file = archive_path.with_suffix(".until-%s.zip" % day.isoformat())

            contents = "%s%s" % (old_archive_contents, new_archive_contents)

            with ZipFile(str(archive_file), 'w', ZIP_DEFLATED) as zf:
                arcname = '%s.until-%s.txt' % (state, day.isoformat())
                zf.writestr(arcname, contents)

            old_history_file.unlink() 
            if yearly_archive:
                yearly_archive.unlink()

            info("archive_history", "Archived history from %s for %s" % (day, thing))
        else:
            info("archive_history", "No history for %s older than %s" % (thing, two_days_ago))

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

        if state_file.exists():
            with state_file.open() as f:
                previous_value = json.loads(f.read())
            result = self._append_history(thing, state, previous_value)
            log_updated.extend(result)
            previous_state = previous_value.get('state', {})
            previous_timestamp = previous_value.get('timestamp_utc', None)
        else:
            previous_state = {}
            previous_timestamp = None

        value = state_processor.explode(value, previous_state, previous_timestamp)
        
        desired_file = self._get_state_path(thing, "desired")
        if not desired_file.exists():
            self.update_desired(thing, value.get('config', {}))
            log_updated.append('created_desired')
        
        displayables = self.load_state(thing, "displayables")

        new_displayables = self._get_new_displayables(value, displayables)
        if len(new_displayables) > 0:
            displayables.update(new_displayables) 
            self.update_displayables(thing, displayables)
            log_updated.append('updated_displayables')

        aliases = flat_map(displayables, 'alias')
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
        from_state = self.load_state(thing, "reported")
        if from_state.get('state') is None or from_state.get('state').get('config') is None:
            error("get_delta", "Unexpected from_state format, expected to begin with state/config. %s %s" % (thing, from_state))
            return {"error":1}
        from_state = from_state['state']['config']

        to_state = self.load_state(thing, "desired")

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
            with state_file.open() as f:
                contents = f.read()

            deserialized = json.loads(contents)
            return deserialized
        else:
            info("load_state", "Tried to load state that does not exist: %s/%s" % (thing, state_name))

            return {}

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

    def update_displayables(self, a_thing, value):
        validate_input(a_thing, "displayables", value)
        if len(list(filter(is_displayable, value.keys()))) != len(value.keys()): 
            error('update_displayables', "Some of the keys are not displayable. Ignoring update. %s %s" % (a_thing, value))
            return

        log_updated = []
        
        thing = self.resolve_thing(a_thing)
        thing_directory = self.directory / thing
        if not thing_directory.exists():
            raise Exception("update_displayables", "Not allowed to create new directory for displayables %s %s" % (thing, value))

        state = "displayables"

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

        info("update_displayables", "[%s] updated %s" % (thing, pretty_list(log_updated)))

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

        if since_days > 1:
            history.extend(self._load_history_for_year(thing, state_name, today.year))
            days_since_start_of_year = today.month * 29 + today.day # approximate, understatement
            if since_days > days_since_start_of_year:
                history.extend(self._load_history_for_year(thing, state_name, today.year - 1))

        history.extend(self._load_history_for_day(thing, state_name, yesterday))
        history.extend(self._load_history_for_day(thing, state_name, today))

        state = self.load_state(thing, state_name)
        history.append(state)
        since_day = datetime.utcnow() - timedelta(days=since_days)
        filtered_history = list(filter(lambda s: parse_isoformat(s['timestamp_utc']) > since_day, history))
        return filtered_history

    def update_plot_background(self, a_thing, svg_bytes):
        thing = self.resolve_thing(a_thing)
        plot_path = self.directory / thing / 'plot.png'
        with plot_path.open('wb') as f:
            f.write(svg_bytes)

