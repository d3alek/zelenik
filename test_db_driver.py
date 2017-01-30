import unittest
from pathlib import Path
import db_driver
from tempfile import TemporaryDirectory
from datetime import date
from zipfile import ZipFile
import json

THING="thing"
BASE_STATE = '{"config": %s}'
FORMAT = '{"state": %s, "timestamp_utc": "2017-01-25 15:34:12.989202"}'
JSN = '{"value": "%s"}' # separate case from BASE_STATE for convenience - notice the " surrounding %s

def timeless(d):
    dc = d.copy()
    if dc.get('timestamp_utc'):
        dc.pop('timestamp_utc') 
    return dc

class TestDatabaseDriver(unittest.TestCase):
    def setUp(self):
        self.db_directory = TemporaryDirectory()
        self.db_location = self.db_directory.name

        self.view_directory = TemporaryDirectory()
        view_location = self.view_directory.name
        index = Path(view_location)  / "index.html"
        index.touch()
        style = Path(view_location) / "style.html"
        style.touch()

        self.db = db_driver.DatabaseDriver(self.db_location, view_location)

    def tearDown(self):
        self.db_directory.cleanup()
        self.view_directory.cleanup()

    def test_update_reported_creates_thing_with_view(self):
        self.when_updating_reported("{}")

        self.then_one_thing()
        self.then_thing_exists()
        self.then_thing_has_view()

    def test_update_reported_applies_format(self):
        self.given_thing()

        self.when_updating_reported(BASE_STATE % JSN % 1)

        self.then_state_exists("reported", FORMAT % BASE_STATE % JSN % 1) 

    def test_first_reported_creates_desired(self):
        self.given_thing()

        self.when_updating_reported(BASE_STATE % JSN % 1)

        self.then_state_exists("desired", JSN % 1) 

    def test_first_reported_creates_aliases(self):
        self.given_thing()

        self.when_updating_reported(BASE_STATE % JSN % 1)

        self.then_state_exists("aliases", JSN % "") 

    def test_update_reported_adds_timestamp(self):
        self.given_thing()

        self.when_updating_reported(JSN % 1)

        self.then_has_timestamp("reported")

    def test_update_reported_adds_timestamp(self):
        self.given_thing()
        self.given_state("desired", JSN % 1)

        self.when_updating_desired(JSN % 2)

        self.then_history_has_timestamp("desired")

    def test_update_updates_state(self):
        self.given_thing()
        self.given_state("reported", FORMAT % JSN % 1)

        self.when_updating_reported(JSN % 2)

        self.then_state_exists("reported", FORMAT % JSN % 2)

    def test_update_stores_history(self):
        self.given_thing()
        self.given_state("reported", FORMAT % JSN % 1)

        self.when_updating_reported(JSN % 2)

        self.then_history_exists("reported", FORMAT % JSN % 1)

    def test_update_appends_to_history(self):
        self.given_thing()
        self.given_state("reported", FORMAT % JSN % 2)
        self.given_history("reported", FORMAT % JSN % 1)

        self.when_updating_reported(JSN % 3)

        self.then_history_exists("reported", "%s\n%s" % (FORMAT % JSN % 1, FORMAT % JSN % 2))

    def test_update_archives_history_from_two_years_ago(self):
        year = date.today().year
        self.given_thing()
        self.given_state("reported", JSN % "old")
        self.given_history("reported", JSN % "oldest", year=year-2)
        self.given_history("reported", JSN % "older", year=year-1)
        self.when_updating_reported(JSN % "new")

        self.then_two_histories("reported")
        self.then_history_exists("reported", JSN % "older", year=year-1)
        self.then_history_exists("reported", JSN % "old")
        self.then_archive_exists("reported", year-2, JSN % "oldest")
        self.then_state_exists("reported", FORMAT % JSN % "new")

    def test_get_delta_no_desired(self):
        json_string = FORMAT % BASE_STATE % '{}'

        self.given_thing()
        self.given_state("reported", json_string)

        self.when_getting_delta()

        self.then_delta_is("{}")

    def test_get_delta_no_difference(self):
        self.given_thing()
        self.given_state("reported", FORMAT % BASE_STATE % '{}')
        self.given_state("desired", '{}')

        self.when_getting_delta()

        self.then_delta_is("{}")

    def test_get_delta_invalid_state(self):
        missing_config_state =  FORMAT % '{"sleep": %d}'

        self.given_thing()
        self.given_state("reported", missing_config_state % 1)
        self.given_state("desired", missing_config_state % 2)

        self.when_getting_delta()

        self.then_delta_is('{"error":1}')

    def test_get_delta_version(self):
        version = '{"version":"%d"}'
        self.when_getting_reported_desired_delta(version, 1, 2)

        self.then_delta_is(version % 2)
    
    def test_get_delta_sleep(self):
        sleep = '{"sleep":"%d"}'
        self.when_getting_reported_desired_delta(sleep, 1, 2)

        self.then_delta_is(sleep % 2)

    def test_get_delta_gpio(self):
        gpio = '{"gpio":{"0":"%s"}}'
        self.when_getting_reported_desired_delta(gpio, "OneWire", "DHT11")

        self.then_delta_is(gpio % "DHT11")

    def test_get_delta_actions(self):
        actions = '{"actions":{"A|I2C-8|4H":"10~%d"}}'
        self.when_getting_reported_desired_delta(actions, 1, 2)

        self.then_delta_is(actions % 2)

    def test_get_delta_multiple(self):
        gpio_actions = '{"gpio": {"0":"%d"}, "actions":{"A|I2C-8|4H":"10~%d"}}'
        self.when_getting_reported_desired_delta(gpio_actions, (1, 1), (2, 2))

        self.then_delta_is(gpio_actions % (2, 2))

    def test_get_delta_multi_level(self):
        multi_level = '{"sleep": "%d", "actions":{"A|I2C-8|4H":"10~%d"}}'
        self.when_getting_reported_desired_delta(multi_level, (1, 1), (2, 2))

        self.then_delta_is(multi_level % (2, 2))

    def test_get_delta_multiple_one_level(self):
        one_level = '{"actions":{"A|I2C-8|4H":"10~%d","A|I2C-9|4L":"5~%d"}}'
        self.when_getting_reported_desired_delta(one_level, (1, 1), (2, 2))

        self.then_delta_is(one_level % (2, 2))

    def test_update_reported_deletes_graph(self):
        self.given_thing()
        self.given_state("reported", BASE_STATE % '{}')
        self.given_graph()

        self.when_updating_reported(JSN % 1)

        self.then_no_graph()

    def given_thing(self):
        p = Path(self.db_location) / THING
        p.mkdir()

    def given_state(self, state, value):
        p = Path(self.db_location) / THING / state
        p = p.with_suffix('.json')
        with p.open('w') as f:
            f.write(value)

    def given_history(self, state, value, year=date.today().year):
        p = Path(self.db_location) / THING / "history"
        if not p.is_dir():
            p.mkdir()
        p = p / state
        p = p.with_suffix('.%d.txt' % year)
        with p.open('w') as f:
            f.write(value)
            f.write('\n')
    
    def given_graph(self):
        p = Path(self.db_location) / THING / "graph.png"
        p.touch()

    def when_updating_desired(self, value):
        self.db.update_desired(THING, json.loads(value)) 

    def when_updating_reported(self, value):
        self.db.update_reported(THING, json.loads(value)) 

    def when_getting_delta(self):
        self.delta = self.db.get_delta(THING)  
    def when_getting_reported_desired_delta(self, base_state_supplement, reported_substitution, desired_substitution):
        state_reported = FORMAT % BASE_STATE % base_state_supplement
        state_desired = base_state_supplement

        self.given_thing()
        self.given_state("reported", state_reported % reported_substitution)
        self.given_state("desired", state_desired % desired_substitution)

        self.when_getting_delta()

    def then_one_thing(self):
        p = Path(self.db_location)
        things = [x for x in p.iterdir()]
        self.assertEqual(len(things), 1)

    def then_thing_exists(self):
        p = Path(self.db_location) / THING
        self.assertTrue(p.exists())

    def then_one_state(self):
        p = Path(self.db_location) / THING
        states = [x for x in p.iterdir() if x.match('*.json')]

        self.assertEqual(len(states), 1)

    def then_state_exists(self, state, value):
        p = Path(self.db_location) / THING / state 
        p = p.with_suffix('.json')
        with p.open() as f:
            contents = timeless(json.loads(f.read()))

        expected_value = timeless(json.loads(value))
        self.assertEqual(contents, expected_value)

    def then_has_timestamp(self, state):
        p = Path(self.db_location) / THING / state 
        p = p.with_suffix('.json')
        with p.open() as f:
            contents = json.loads(f.read())

        self.assertTrue(contents.get('timestamp_utc'))

    def then_history_has_timestamp(self, state):
        p = Path(self.db_location) / THING / 'history' / state 
        p = p.with_suffix('.%d.txt' % date.today().year)
        with p.open() as f:
            contents = json.loads(f.read())

        self.assertTrue(contents.get('timestamp_utc'))


    def then_two_histories(self, state):
        p = Path(self.db_location) / THING / "history"
        histories = [x for x in p.iterdir() if x.match('%s*' % state)]
        self.assertEqual(len(histories), 2)

    def then_history_exists(self, state, value, year = date.today().year):
        p = Path(self.db_location) / THING / "history" / state 
        p = p.with_suffix('.%d.txt' % year)
        with p.open() as f:
            lines = f.readlines()
            actual = [timeless(json.loads(line)) for line in lines]
        values = value.split('\n')
        expected = [timeless(json.loads(value)) for value in values]
        self.assertEqual(actual, expected)

    def then_archive_exists(self, state, year, value):
        p = Path(self.db_location) / THING / "history" / "archive" / state 
        p = p.with_suffix('.%d.zip' % year)
        file_name = "%s.%d.txt" % (state, year)
        with ZipFile(str(p)) as zf:
            byte_text = zf.read(file_name)
            text = byte_text.decode('utf-8')
            self.assertEqual(text.strip(), value)

    def then_delta_is(self, delta_string):
        self.assertEqual(json.loads(self.delta), json.loads(delta_string))

    def then_thing_has_view(self):
        p = Path(self.db_location) / THING / "index.html"
        self.assertTrue(p.exists())

    def then_no_graph(self):
        p = Path(self.db_location) / THING / "graph.png"
        self.assertFalse(p.exists())




if __name__ == '__main__':
    unittest.main()
