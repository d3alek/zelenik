import unittest
import enchanter
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from db_driver import DatabaseDriver, timestamp
from test_db_driver import timeless

import time

THING="thing"
THING2="another-thing"
SCALE_CONFIG = {"I2C-8-scaled":{"formula": "scale", "from": "I2C-8", "from_low": 0, "from_high": 1024, "to_low": 0, "to_high": 100}}
DECORRELATE_CONFIG = {"I2C-8-decorrelated":{"formula": "decorrelate", "from": "I2C-8-scaled", "correlated": "OW-1", "adjustment": -30, "scale": 6}}

DECORRELATE_CONFIG_FROM_THING2 = {"I2C-8-decorrelated":{"formula": "decorrelate", "from": "I2C-8-scaled", "correlated": "another-thing:OW-1", "adjustment": -30, "scale": 6}}

AVERAGE_CONFIG = {"OW-average": {"formula": "average", "from": ["OW-1", "another-thing:OW-2"]}}

CUM_AVERAGE_CONFIG = {"cum-average": {"formula": "cum_average", "from": "OW-1"}}

CUM_AVERAGE_RESET_CONFIG = {"cum-average": {"formula": "cum_average", "from": "OW-1", "reset_at": "01:00"}}


DISP = {"alias":"","color":"purple","position":"0,0","type":"number","plot":"yes","graph":"yes"}

def colored(d, color):
    c = dict(d)
    c['color'] = color
    return c

def aliased(d, alias):
    a = dict(d)
    a['alias'] = alias
    return a

from datetime import datetime, timedelta

def yesterday():
    return datetime.utcnow() - timedelta(days=1)

def today():
    return datetime.utcnow()

def state(d, time=today()):
    return {"state": d, "timestamp_utc": timestamp(time)}

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

    def test_first_enchant_creates_displayables(self):
        reported = senses({"1": 0})
        self.given_state("reported", state(reported))

        self.when_enchanting()

        displayables = {"1": DISP}
        self.then_state_exists("displayables", displayables) 

    def test_enchant_updates_displayables(self):
        self.given_state("displayables", {"a": DISP})

        self.given_state("reported", state(senses({"a":1, "c": 2})))
        self.when_enchanting()

        self.then_state_exists("displayables", {"a": colored(DISP, 'purple'),"c": colored(DISP, 'green')}) 

    def test_enchant_updates_displayables_without_other_thing_senses(self):
        self.given_state("displayables", {"a": DISP})

        self.given_state("reported", state(senses({"a":1, "c": 2, 'other-thing:d': 3})))
        self.when_enchanting()

        self.then_state_exists("displayables", {"a": colored(DISP, 'purple'),"c": colored(DISP, 'green')}) 



    def test_enchant_includes_alias(self):
        self.given_alias("a", "temperature")

        self.given_state("reported", state(senses({"a":1})))

        self.when_enchanting()

        self.then_enchanted(state(senses({"a":{"value": 1, "alias": "temperature"}})))

    def test_enchant_scale_to_percent_by_default(self):
        reported_senses = {"I2C-8": {"value": 512}}

        enchanted = senses(updated(reported_senses, {"I2C-8-percent": 50}))
        self.given_state("reported", state(senses(reported_senses)))

        self.when_enchanting(alias=False)

        self.then_enchanted(state(enchanted))

    def test_enchant_accepts_number_values(self):
        self.given_config(SCALE_CONFIG)

        reported_senses = {"I2C-8": 512}
        reported = senses(reported_senses)
        enchanted = senses(updated(reported_senses, {"I2C-8-scaled": 50}))

        self.given_state("reported", state(reported))

        self.when_enchanting(alias=False)

        self.then_enchanted(state(enchanted))

    def test_enchant_falls_back_to_expected(self):
        self.given_config(SCALE_CONFIG)

        reported_senses = {"I2C-8": {"expected": 512}}
        reported = senses(reported_senses)
        enchanted = senses(updated(reported_senses, {"I2C-8-scaled": 50}))

        self.given_state("reported", state(reported))
        self.when_enchanting(alias=False)

        self.then_enchanted(state(enchanted))

    def test_enchant_ignores_no_value_senses(self):
        self.given_config(SCALE_CONFIG)

        reported_senses = {"I2C-8": {"ssd": 512}}
        reported = senses(reported_senses)

        self.given_state("reported", state(reported))
        self.when_enchanting(alias=False)

        self.then_enchanted(state(reported))

    def test_enchant_scale(self):
        self.given_config(SCALE_CONFIG)

        reported_senses = {"I2C-8": {"value": 512}}
        reported = senses(reported_senses)
        enchanted = senses(updated(reported_senses, {"I2C-8-scaled": 50}))

        self.given_state("reported", state(reported))
        self.when_enchanting(alias=False)

        self.then_enchanted(state(enchanted))

    def test_enchant_decorrelate_temperature(self):
        self.given_config(updated(SCALE_CONFIG, DECORRELATE_CONFIG))

        reported_senses = {"I2C-8": {"value": 512}, "OW-1": {"value": 35}}
        reported = senses(reported_senses)
        enchanted = senses(updated(reported_senses, {"I2C-8-scaled": 50, "I2C-8-decorrelated": 20}))

        self.given_state("reported", state(reported))
        self.when_enchanting(alias=False)

        self.then_enchanted(state(enchanted))

    def test_decorrelate_temperature_no_temperature(self):
        self.given_config(updated(SCALE_CONFIG, DECORRELATE_CONFIG))

        reported_sense = {"I2C-8": {"value": 512}}
        reported = senses(reported_sense)
        enchanted = senses(updated(reported_sense, {"I2C-8-scaled": 50}))

        self.given_state("reported", state(reported))
        self.when_enchanting(alias=False)

        self.then_enchanted(state(enchanted))

    def test_decorrelate_temperature_from_another_thing(self):
        self.given_config(updated(SCALE_CONFIG, DECORRELATE_CONFIG_FROM_THING2))
        self.given_state('enchanted', state(senses({'OW-1': 35})), thing=THING2)

        reported_sense = {"I2C-8": {"value": 512}}
        reported = senses(reported_sense)
        enchanted = senses(updated(reported_sense, {"I2C-8-scaled": 50, "I2C-8-decorrelated": 20, "%s:OW-1" % THING2: 35}))

        self.given_state("reported", state(reported))
        self.when_enchanting(alias=False)

        self.then_enchanted(state(enchanted))


    def test_average(self):
        self.when_calculating_average([15, 15, 30])

        self.then_average(20)

    def test_cum_average(self):
        self.when_calculating_cum_average(new=25, old=24, old_count=1)

        self.then_cum_average((24.5, 2))

    def test_enchanter_average(self):
        self.given_config(AVERAGE_CONFIG)
        self.given_state('reported', state(senses({'OW-1': 15})), thing=THING)
        self.given_state('enchanted', state(senses({'OW-2': 25})), thing=THING2)

        self.when_enchanting(alias=False)

        self.then_enchanted(state(senses({'OW-1': 15, '%s:OW-2' % THING2: 25, 'OW-average': 20})))

    def test_enchanter_cum_average(self):
        self.given_config(CUM_AVERAGE_CONFIG)
        self.given_state('enchanted', state(senses({'cum-average': {"value":24, "count": 1}})))
        self.given_state('reported', state(senses({'OW-1': 25})))

        self.when_enchanting(alias=False)

        self.then_enchanted(state(senses({'OW-1': 25, 'cum-average': {"value":24.5, "count": 2}})))

    def test_enchanter_cum_average_resets(self):
        self.given_config(CUM_AVERAGE_RESET_CONFIG)
        self.given_state('enchanted', state(senses({'cum-average': {"value":24, "count": 1}}), yesterday()))
        self.given_state('reported', state(senses({'OW-1': 25}), today()))

        self.when_enchanting(alias=False)

        self.then_enchanted(state(senses({'OW-1': 25, 'cum-average': {"value":25, "count": 1}})))

    def given_state(self, state, value, thing=THING):
        thing_directory = self.db_directory / thing
        if not thing_directory.is_dir():
            thing_directory.mkdir()
        p = thing_directory / state
        p = p.with_suffix('.json')
        with p.open('w') as f:
            f.write(json.dumps(value))

    def given_config(self, config):
        p = self.db_directory / THING / "enchanter.json"
        
        with p.open('w') as f:
            f.write(json.dumps(config))

    def given_alias(self, key, value):
        p = self.db_directory / THING / "displayables.json"
        
        with p.open('w') as f:
            f.write(json.dumps({key : aliased(DISP, value)}))

    def when_calculating_average(self, values):
        self.average = enchanter.average(values)

    def when_calculating_cum_average(self, new, old, old_count):
        self.cum_average = enchanter.cum_average(new, old, old_count)

    def when_updating_reported(self, reported):
        self.db.update_reported(THING, reported)

    def when_enchanting(self, thing=THING, alias=True):
        self.enchanted = self.enchanter.enchant(thing, alias=alias)

    def when_scaling(self, value, from_low, from_high, to_low, to_high):
        self.scaled = enchanter.scale(value, from_low, from_high, to_low, to_high)

    def when_decorrelating(self, value, correlated, adjustment, scale):
        self.decorrelated = enchanter.decorrelate(value, correlated, adjustment, scale)

    def then_average(self, expected):
        self.assertEqual(expected, self.average)

    def then_cum_average(self, expected):
        self.assertEqual(expected, self.cum_average)

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

if __name__ == '__main__':
    unittest.main()
