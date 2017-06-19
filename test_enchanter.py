import unittest
import enchanter
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from db_driver import DatabaseDriver
from test_db_driver import timeless

import time


THING="thing"
THING2="another-thing"
SCALE_CONFIG = {"I2C-8-scaled":{"formula": "scale", "from": "I2C-8", "from_low": 0, "from_high": 1024, "to_low": 0, "to_high": 100}}
DECORRELATE_CONFIG = {"I2C-8-decorrelated":{"formula": "decorrelate", "from": "I2C-8-scaled", "correlated": "OW-1", "adjustment": -30, "scale": 6}}

DECORRELATE_CONFIG_FROM_THING2 = {"I2C-8-decorrelated":{"formula": "decorrelate", "from": "I2C-8-scaled", "correlated": "another-thing:OW-1", "adjustment": -30, "scale": 6}}

def state(d):
    return {"state": d, "timestamp_utc": "none"}

def senses(d):
    return {"senses": d}

def updated(d, update):
    ret = dict(d)
    ret.update(update)
    return ret

class TestEnchanter(unittest.TestCase):
    def setUp(self):
        self.tmp_directory = TemporaryDirectory()
        self.enchanter = enchanter.Enchanter(self.tmp_directory.name)
        self.db = DatabaseDriver(self.tmp_directory.name)

        self.db_directory = Path(self.tmp_directory.name) / 'db'
        self.db_directory.mkdir()
        thing_directory = self.db_directory / THING
        thing_directory.mkdir()

        self.enchanter.start()
        self.config = {}

    def tearDown(self):
        self.enchanter.stop()
        self.tmp_directory.cleanup()

    def test_scale_up(self):
        self.when_scaling(50, 0, 100, 0, 1024)

        self.then_scaled(512)

    def test_scale_down(self):
        self.when_scaling(512, 0, 1024, 0, 100)

        self.then_scaled(50)

    def test_decorrelate(self):
        self.when_decorrelating(30, 20, -19, 10)

        self.then_decorrelated(20)

    def test_enchants_on_reported_file_changed(self):
        reported = senses({"OW-1": {"value": 35}})
        self.when_updating_reported(reported)

        time.sleep(2) # as enchanter runs once a second

        self.then_state_exists('enchanted', {'state': reported})

    def test_enchant_scale_to_percent_by_default(self):
        reported_senses = {"I2C-8": {"value": 512}}
        reported = senses(reported_senses)
        self.when_updating_reported(reported)

        time.sleep(2) # as enchanter runs once a second

        enchanted = senses(updated(reported_senses, {"I2C-8-percent": 50}))

        self.then_state_exists('enchanted', {'state': enchanted})

    def test_enchant_scale(self):
        self.given_config(SCALE_CONFIG)

        reported_senses = {"I2C-8": {"value": 512}}
        reported = senses(reported_senses)
        enchanted = senses(updated(reported_senses, {"I2C-8-scaled": 50}))

        self.when_enchanting(state(reported))

        self.then_enchanted(state(enchanted))

    def test_enchant_decorrelate_temperature(self):
        self.given_config(updated(SCALE_CONFIG, DECORRELATE_CONFIG))

        reported_senses = {"I2C-8": {"value": 512}, "OW-1": {"value": 35}}
        reported = senses(reported_senses)
        enchanted = senses(updated(reported_senses, {"I2C-8-scaled": 50, "I2C-8-decorrelated": 20}))

        self.when_enchanting(state(reported))

        self.then_enchanted(state(enchanted))

    def test_decorrelate_temperature_no_temperature(self):
        self.given_config(updated(SCALE_CONFIG, DECORRELATE_CONFIG))

        reported_sense = {"I2C-8": {"value": 512}}
        reported = senses(reported_sense)
        enchanted = senses(updated(reported_sense, {"I2C-8-scaled": 50}))

        self.when_enchanting(state(reported))

        self.then_enchanted(state(enchanted))

    def test_decorrelate_temperature_from_another_thing(self):
        self.given_config(updated(SCALE_CONFIG, DECORRELATE_CONFIG_FROM_THING2))
        self.given_state('reported', state(senses({'OW-1': 35})), thing=THING2)

        reported_sense = {"I2C-8": {"value": 512}}
        reported = senses(reported_sense)
        enchanted = senses(updated(reported_sense, {"I2C-8-scaled": 50, "I2C-8-decorrelated": 20}))

        self.when_enchanting(state(reported))

        self.then_enchanted(state(enchanted))

    def given_state(self, state, value, thing=THING):
        thing_directory = self.db_directory / thing
        if not thing_directory.is_dir():
            thing_directory.mkdir()
        p = thing_directory / state
        p = p.with_suffix('.json')
        with p.open('w') as f:
            f.write(json.dumps(value))

    def given_config(self, config):
        self.config = config

    def when_updating_reported(self, reported):
        self.db.update_reported(THING, reported)

    def when_enchanting(self, reported):
        self.enchanted = self.enchanter.enchant(reported, self.config)

    def when_scaling(self, value, from_low, from_high, to_low, to_high):
        self.scaled = enchanter.scale(value, from_low, from_high, to_low, to_high)

    def when_decorrelating(self, value, correlated, adjustment, scale):
        self.decorrelated = enchanter.decorrelate(value, correlated, adjustment, scale)

    def then_scaled(self, expected):
        self.assertEqual(expected, self.scaled)

    def then_decorrelated(self, expected):
        self.assertEqual(expected, self.decorrelated)

    def then_state_exists(self, state, expected_value):
        p = self.db_directory / THING / state 
        p = p.with_suffix('.json')
        with p.open() as f:
            contents = json.loads(f.read())

        self.assertEqual(timeless(expected_value), timeless(contents))

    def then_enchanted(self, expected_json):
        self.assertEqual(timeless(expected_json), timeless(self.enchanted))
#
## explode
#    elif sense in RESISTIVE_MOISTURE_SENSES:
#        threshold = resistive_humidity_to_percent(threshold)
#        delta = resistive_humidity_to_percent(delta)
#
#    elif sense == "I2C-32c":
#        threshold = scale_capactive_humidity(threshold)
#        delta = capacitive_humidity_to_percent(delta)
#
## compact
#    elif sense in RESISTIVE_MOISTURE_SENSES:
#        threshold = resistive_humidity_to_analog(threshold)
#        delta = resistive_humidity_to_analog(delta)
#    elif sense == "I2C-32c":
#        threshold = capacitive_humidity_to_analog(threshold)
#        delta = capacitive_humidity_to_analog(delta)
#
#def capacitive_humidity_to_percent(value):
#    return scale_to_percent(value, 300, 800)
#
#def resistive_humidity_to_percent(value):
#    return scale_to_percent(value, 0, 800)
#
#def capacitive_humidity_to_analog(value):
#    return scale_to_analog(value, 300, 800)
#
#def resistive_humidity_to_analog(value):
#    return scale_to_analog(value, 0, 800)
#
#def scale_to_percent(value, low, high):
#    normalized = (value - low) / (high - low)
#    normalized = normalized * 100
#    if normalized < 0:
#        normalized = 0
#    elif normalized > 100:
#        normalized = 100
#    
#    return normalized
#
#def scale_to_analog(value, low, high):
#    normalized = value / 100
#    normalized = int(normalized * (high - low) + low)
#
#    if normalized < 0:
#        normalized = 0
#    elif normalized > 1024:
#        normalized = 1024
#    
#    return normalized
#
#def normalize(value, scale_function):
#    return scale_function(value) 
#
#
#        if key == 'I2C-32c' or key in RESISTIVE_MOISTURE_SENSES:
#            if key == 'I2C-32c':
#                transform = capacitive_humidity_to_percent
#            else:
#                transform = resistive_humidity_to_percent
#
#            to_normalize = None
#            value = enriched_sense.get('value', None)
#            if value is not None:
#                enriched_sense['normalized'] = normalize(value, transform)
#
#            expected = enriched_sense.get('expected', None)
#            if expected is not None:
#                enriched_sense['expected-normalized'] = normalize(expected, transform)
#
#
#

if __name__ == '__main__':
    unittest.main()
