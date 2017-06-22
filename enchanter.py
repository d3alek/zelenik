#!/www/zelenik/venv/bin/python

import matplotlib._color_data as mcd

from logger import Logger
import db_driver
from db_driver import pretty_json, SHOULD_ENCHANT_FLAG, flat_map, is_displayable

from numbers import Number

from state_processor import parse_isoformat

import re
import json
import time

import threading 

from pathlib import Path

from datetime import datetime, timedelta, time

logger = Logger("enchanter")

DIR = '/www/zelenik/'
ANALOG_SENSES = {'I2C-8', 'I2C-9', 'I2C-10'}

NEW_DISPLAYABLE = {"alias":"", "color": "green", "position":"0,0","type":"number","plot":"yes","graph":"yes"}

def parse_time(s):
    return datetime.strptime(s, "%H:%M").time()

def today_midnight(now):
    return datetime.combine(today(now), time(0))

def today(now):
    return now.date()

def today_at(t, now):
    return datetime.combine(today(now), t) 

def prefix_keys(prefix, d):
    dd = {}
    for key, value in d.items():
        dd[prefix+key] = value
    return dd

def set_subtract(subtract_from, to_subtract):
    return [item for item in subtract_from if item not in to_subtract]

def get_only_element(l):
    if len(l) > 1:
        raise Exception('Expected %s to have only 1 element' % l)

    return l[0]

# source: https://blog.xkcd.com/2010/05/03/color-survey-results/, not using xkcd variant because we also need them in CSS
COLORS = list(reversed(['purple', 'green', 'blue', 'pink', 'brown', 'red', 'teal', 'orange', 'magenta', 'yellow', 'grey', 'violet', 'turquoise', 'lavender', 'tan', 'cyan', 'aqua', 'maroon', 'olive', 'salmon', 'beige', 'black', 'lime', 'indigo']))

def get_value(sense):
    if sense is None:
        return None
    if isinstance(sense, Number):
        return sense
    elif 'value' in sense:
        return sense['value']
    elif 'expected' in sense:
        return sense['expected']

    return None

def scale(value, from_low, from_high, to_low, to_high):
    return ((value - from_low) / (from_high - from_low)) * (to_high - to_low) + to_low

def decorrelate(value, correlated, adjustment, scale):
    return value - (correlated + adjustment) * scale

def average(values):
    return sum(values)/len(values)


# source: https://en.wikipedia.org/wiki/Moving_average#Cumulative_moving_average
def cum_average(new, old, old_count):
    count = old_count + 1
    
    return (new + old_count * old) / count, count


class Enchanter:
    def __init__(self, working_directory = DIR):
        self.working_directory = working_directory
        self.db = db_driver.DatabaseDriver(working_directory)

        self.db_path = Path(self.working_directory) / 'db'

    def enchant_all(self):
        log = logger.of('enchant_all')
        if not self.running:
            return
        if not self.db_path.is_dir():
            log.error('Database path %s is not a directory.' % self.db_path)
            self.stop()
            return

        for thing_path in self.db_path.iterdir():
            thing = thing_path.name
            if thing in ('na', 'stado'):
                continue
            self.enchant_thing(thing)

        if self.running:
            t = threading.Timer(1, self.enchant_all)
            t.start()

    def start(self):
        logger.of('start').info('Starting')
        self.running = True
        t = threading.Timer(1, self.enchant_all)
        t.start()

    def stop(self):
        logger.of('stop').info('Stopping')
        self.running = False

    def create_default_config(self, thing, reported):
        config = {}
        senses = reported['state']['senses']

        analog_senses = ANALOG_SENSES.intersection(senses.keys())
        for analog_sense in analog_senses:
            key = '%s-percent' % analog_sense
            config[key] = {'formula': 'scale', 'from': analog_sense, 'from_low': 0, 'from_high': 1024, 'to_low': 0, 'to_high': 100}


        self.db.update_enchanter(thing, config)

    def _get_new_displayables(self, state, previous_displayables):
        new_displayables = {}
        senses = state['state'].get('senses', {})
        write = state['state'].get('write', {})
        keys = set().union(senses).union(write)
        keys = sorted(filter(is_displayable, keys))
        previous_keys = previous_displayables.keys()
        log = logger.of('_get_new_displayables')
        used_colors = flat_map(previous_displayables, "color").values()
        unused_colors = set_subtract(COLORS, used_colors)
        for key in keys:
            if key not in previous_keys:
                if not unused_colors:
                    log = logger.of('_get_new_displayables')
                    log.error("No more unused colors. Starting to repeat")
                    unused_colors = list(COLORS)

                new_displayables[key] = dict(NEW_DISPLAYABLE)
                if ':' in key:
                    # ignoring another thing's sense
                    continue
                if key == 'A0':
                    new_displayables[key]['color'] = 'yellow'
                    new_displayables[key]['type'] = 'percent'
                    new_displayables[key]['alias'] = 'светлина'
                else: 
                    if key.startswith('OW-'):
                        new_displayables[key]['type'] = 'temp'
                    # Do not display raw I2C data in graph or plot
                    if key.startswith('I2C-'): 
                        new_displayables[key]['alias'] = key.split('-')[1]
                        new_displayables[key]['graph'] = 'no'
                        new_displayables[key]['plot'] = 'no'
                    if key.endswith('-percent'):
                        new_displayables[key]['type'] = 'percent'
                        new_displayables[key]['graph'] = 'yes'
                        new_displayables[key]['plot'] = 'yes'
                    if key in ['4', '5', '13']:
                        new_displayables[key]['type'] = 'switch'
                    if new_displayables[key]['graph'] == 'yes' or new_displayables[key]['plot'] == 'yes':
                        new_displayables[key]['color'] = unused_colors.pop()
                

        return new_displayables

    def enchant_thing(self, thing):
        log = logger.of('enchant_thing')
        thing_path = Path(self.working_directory) / 'db' / thing
        should_enchant = thing_path / SHOULD_ENCHANT_FLAG
        if not should_enchant.exists():
            return

        log.info('Enchanting %s' % thing)

        enchanted = self.enchant(thing)

        enchanted_path = thing_path / 'enchanted.json'
        with enchanted_path.open('w') as f:
            f.write(pretty_json(enchanted))

        should_enchant.unlink()

    # Keep this fast as graph runs it on every reported state
    def enchant(self, thing, reported=None, config=None, displayables=None, alias=True, old_enchanted=None):
        log = logger.of('enchant')

        if reported is None:
            reported = self.db.load_state(thing, 'reported')

        if config is None:
            config = self.db.load_state(thing, 'enchanter')
            if not config:
                log.info('Config is empty, making a default one')
                self.create_default_config(thing, reported)
                config = self.db.load_state(thing, 'enchanter')

        if old_enchanted is None:
            old_enchanted = self.db.load_state(thing, 'enchanted')

        enchanted = dict(reported)
        senses = enchanted['state']['senses']
        now = parse_isoformat(enchanted['timestamp_utc'])

        old_enchanted_senses = old_enchanted.get('state', {}).get('senses', {})
        old_time_string = old_enchanted.get('timestamp_utc')
        if old_time_string is None:
            old_time = today_midnight(now)
        else:
            old_time = parse_isoformat(old_time_string)

        for name, value in config.items():
            self.apply_formula(name, value, senses, old_enchanted_senses, old_time, now)

        if alias:
            if displayables is None:
                displayables = self.db.load_state(thing, "displayables")

                new_displayables = self._get_new_displayables(enchanted, displayables)
                if len(new_displayables) > 0:
                    displayables.update(new_displayables) 
                    self.db.update_displayables(thing, displayables)

            aliases = flat_map(displayables, 'alias')
            enchanted_aliased = self.db._apply_aliases(thing, enchanted, aliases = aliases)
            return enchanted_aliased

        return enchanted

    # Modifying senses - using it as a cache
    def retrieve_sense_value(self, key, senses = {}):
        log = logger.of('retrieve_sense_value')
        
        if key not in senses:
            if ':' not in key:
                log.error('Could not retrieve sense value because key %s missing in senses %s' % (key, senses))
                return None

            split = key.split(':')
            a_thing = split[0]
            thing = self.db.resolve_thing(a_thing)
            sense_key = split[1]

            log.info('Loading senses for %s' % thing)
            state = self.db.load_state(thing, 'enchanted')
            thing_senses = state.get('state', {}).get('senses')
            if thing_senses is None:
                log.info('No senses found for %s, making an empty record to prevent loading again this turn' % thing)
                thing_senses = {}
            senses.update(prefix_keys('%s:' % a_thing, thing_senses))

        return get_value(senses.get(key))

    """
    * known formula - config *
        scale - from_low, from_high, to_low, to_high
        decorrelate - correlation (may be from another thing, format is thing:sense_key, adjustment, scale
        average - from (a list)
        cum_average - from, start_time, end_time
    """
    def apply_formula(self, key, formula_config, senses, old_enchanted_senses, old_time, now):
        log = logger.of('apply_formula')

        from_keys = formula_config['from']
        if not isinstance(from_keys, list):
            from_keys = [from_keys]
        from_sense_values = list(map(lambda k: self.retrieve_sense_value(k, senses = senses), from_keys))

        if None in from_sense_values:
            log.error('Not applying formula %s because at least one from value missing: %s' % (formula_config, from_sense_values))
            return 

        formula = formula_config['formula']

        if formula == 'scale':
            from_value = get_only_element(from_sense_values)
            from_low = formula_config['from_low']
            from_high = formula_config['from_high']
            to_low = formula_config['to_low']
            to_high = formula_config['to_high']
            senses[key] = scale(from_value, from_low, from_high, to_low, to_high)
        elif formula == 'decorrelate':
            from_value = get_only_element(from_sense_values)
            correlated = formula_config['correlated']
            correlated_sense = self.retrieve_sense_value(correlated, senses)
                 
            if correlated_sense is None:
                log.info('Not decorrelating because of missing %s' % correlated)
                return

            correlated_value = get_value(correlated_sense)

            adjustment = formula_config['adjustment']
            correlation_scale = formula_config['scale']

            senses[key] = decorrelate(from_value, correlated_value, adjustment, correlation_scale)

        elif formula == 'average':
            senses[key] = average(from_sense_values)

        elif formula == 'cum_average':
            reset_at_string = formula_config.get('reset_at')

            if reset_at_string is None:
                reset_at = None
            else:
                reset_at = today_at(parse_time(reset_at_string), now=now)

            old = old_enchanted_senses.get(key)
            if old is None or (reset_at and old_time <= reset_at and reset_at < now):
                log.info("Starting new cumulative average at %s" % now )
                old_value = 0
                old_count = 0
            else:
                old_value = old.get('value', 0)
                old_count = old.get('count', 0)
             
            from_value = get_only_element(from_sense_values)
            value, count = (cum_average(from_value, old_value, old_count))
            senses[key] = {'value': value, 'count': count}

        else:
            log.error('Do not know how to apply formula %s' % formula)
            
if __name__ == '__main__':
    enchanter = Enchanter()
    enchanter.start()
