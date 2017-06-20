#!/www/zelenik/venv/bin/python

from matplotlib import colors

from logger import Logger
import db_driver
from db_driver import pretty_json, SHOULD_ENCHANT_FLAG, flat_map, is_displayable

from numbers import Number

import re
import json
import time

import threading 

from pathlib import Path

logger = Logger("enchanter")

DIR = '/www/zelenik/'
ANALOG_SENSES = {'I2C-8', 'I2C-9', 'I2C-10'}

NEW_DISPLAYABLE = {"alias":"", "color": "green", "position":"0,0","type":"number","plot":"yes","graph":"yes"}


def set_subtract(subtract_from, to_subtract):
    return [item for item in subtract_from if item not in to_subtract]


FIRST_COLORS = ['green', 'red', 'blue', 'purple', 'brown', 'orange']
COLORS = list(reversed(FIRST_COLORS + set_subtract(colors.cnames.keys(), FIRST_COLORS))) # revsersing because the intended use is to instantiate a new list and pop out

def get_value(sense):
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

    def enchant_thing(self, thing):
        log = logger.of('enchant_thing')
        thing_path = Path(self.working_directory) / 'db' / thing
        should_enchant = thing_path / SHOULD_ENCHANT_FLAG
        if not should_enchant.exists():
            return

        should_enchant.unlink()

        log.info('Enchanting %s' % thing)

        reported = self.db.load_state(thing, 'reported')
        config = self.db.load_state(thing, 'enchanter')
        enchanted = self.enchant(thing, reported, config)

        displayables = self.db.load_state(thing, "displayables")

        new_displayables = self._get_new_displayables(enchanted, displayables)
        if len(new_displayables) > 0:
            displayables.update(new_displayables) 
            self.db.update_displayables(thing, displayables)

        aliases = flat_map(displayables, 'alias')
        enchanted_aliased = self.db._apply_aliases(thing, enchanted, aliases = aliases)

        enchanted_path = thing_path / 'enchanted.json'
        with enchanted_path.open('w') as f:
            f.write(pretty_json(enchanted_aliased))

    def enchant(self, thing, reported, config):
        log = logger.of('enchant')
        if not config:
            log.info('Config is empty, making a default one')
            self.create_default_config(thing, reported)
            config = self.db.load_state(thing, 'enchanter')

        enchanted = dict(reported)
        senses = enchanted['state']['senses']
        for name, value in config.items():
            result = self.apply_formula(value, senses)
            if result:
                senses[name] = result



        return enchanted 

    """
    * known formula - config *
        scale - from_low, from_high, to_low, to_high
        decorrelate - correlation (may be from another thing, format is thing:sense_key, adjustment, scale
    """
    def apply_formula(self, formula_config, senses):
        log = logger.of('apply_formula')

        from_key = formula_config['from']
        sense = senses.get(from_key, None)
        if not sense:
            log.info('Not enchanting because from missing %s' % from_key)
            return None
        formula = formula_config['formula']
        value = get_value(sense)
        if value == None:
            log.error('Not enchanting because value could not be extracted from %s' % sense)
            return None

        if formula == 'scale':
            from_low = formula_config['from_low']
            from_high = formula_config['from_high']
            to_low = formula_config['to_low']
            to_high = formula_config['to_high']
            return scale(value, from_low, from_high, to_low, to_high)
        elif formula == 'decorrelate':
            correlated = formula_config['correlated']
            if ':' in correlated:
                split = correlated.split(':')
                correlated_thing = split[0]
                correlated_sense_key = split[1]
                log.info('Searching for %s in %s' % (correlated_sense_key, correlated_thing ))

                correlated_state = self.db.load_state(correlated_thing, 'reported')
                
                correlated_senses = correlated_state['state']['senses']
                correlated_sense = correlated_senses.get(correlated_sense_key, None)
            else:
                correlated_sense = senses.get(correlated, None)
                 
            if not correlated_sense:
                log.info('Not decorrelating because of missing %s' % correlated)
                return None
            correlated_value = get_value(correlated_sense)

            adjustment = formula_config['adjustment']
            correlation_scale = formula_config['scale']

            return decorrelate(value, correlated_value, adjustment, correlation_scale)

        else:
            log.error('Do not know how to apply formula %s' % formula)
            return None
            

if __name__ == '__main__':
    enchanter = Enchanter()
    enchanter.start()
