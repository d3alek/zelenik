#!/www/zelenik/venv/bin/python

from logger import Logger
import db_driver
from db_driver import pretty_json, SHOULD_ENCHANT_FLAG

from numbers import Number

import re
import json
import time

import threading 

from pathlib import Path

logger = Logger("enchanter")

DIR = '/www/zelenik/'
ANALOG_SENSES = {'I2C-8', 'I2C-9', 'I2C-10'}

def get_value(sense):
    if isinstance(sense, Number):
        return sense
    else:
        return sense['value']

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
        if not config:
            log.info('Config is empty, making a default one')
            self.create_default_config(thing, reported)
            config = self.db.load_state(thing, 'enchanter')

        enchanted = self.enchant(reported, config)

        enchanted_path = thing_path / 'enchanted.json'
        with enchanted_path.open('w') as f:
            f.write(pretty_json(enchanted))

    def enchant(self, reported, config):
        log = logger.of('enchant')
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
