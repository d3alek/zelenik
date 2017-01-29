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

    def test_update_creates_thing(self):
        self.when_updating("state", "{}")

        self.then_one_thing()
        self.then_thing_exists()

    def test_created_thing_has_view(self):
        self.when_updating("state", "{}")

        self.then_thing_has_view()

    def test_update_creates_state(self):
        self.given_thing()

        self.when_updating("state", JSN % 1)

        self.then_one_state()
        self.then_state_exists("state", JSN % 1) 

    def test_update_adds_timestamp(self):
        self.given_thing()

        self.when_updating("state", JSN % 1)

        self.then_has_timestamp("state")

    def test_update_time_is_an_arrow(self):
        self.given_thing()

        self.when_updating("desired", JSN % 1)
        self.when_updating("reported", JSN % 2)
        self.when_updating("another", JSN % 3)

        self.then_updated_more_recently("reported", "desired")
        self.then_updated_more_recently("another", "reported")
        self.then_updated_more_recently("another", "desired")

    def test_update_updates_state(self):
        self.given_thing()
        self.given_state("state", JSN % 1)

        self.when_updating("state", JSN % 2)

        self.then_one_state()
        self.then_state_exists("state", JSN % 2)

    def test_update_stores_history(self):
        self.given_thing()
        self.given_state("state", JSN % 1)

        self.when_updating("state", JSN % 2)

        self.then_history_exists("state", JSN % 1)

    def test_update_appends_to_history(self):
        self.given_thing()
        self.given_state("state", JSN % 2)
        self.given_history("state", JSN % 1)

        self.when_updating("state", JSN % 3)

        self.then_history_exists("state", "%s\n%s" % (JSN % 1, JSN % 2))

    def test_update_archives_history_from_two_years_ago(self):
        year = date.today().year
        self.given_thing()
        self.given_state("state", JSN % "old")
        self.given_history("state", JSN % "oldest", year=year-2)
        self.given_history("state", JSN % "older", year=year-1)
        self.when_updating("state", JSN % "new")

        self.then_two_histories("state")
        self.then_archive_exists("state", year-2, JSN % "oldest")
        self.then_history_exists("state", JSN % "older", year=year-1)
        self.then_history_exists("state", JSN % "old")
        self.then_state_exists("state", JSN % "new")

    def test_get_delta_no_desired(self):
        json_string = FORMAT % BASE_STATE % '{}'

        self.given_thing()
        self.given_state("reported", json_string)

        self.when_getting_delta("reported", "desired")

        self.then_delta_is("{}")

    def test_get_delta_no_difference(self):
        same_json_string = FORMAT % BASE_STATE % '{}'

        self.given_thing()
        self.given_state("reported", same_json_string)
        self.given_state("desired", same_json_string)

        self.when_getting_delta("reported", "desired")

        self.then_delta_is("{}")

    def test_get_delta_invalid_state(self):
        missing_config_state =  FORMAT % '{"sleep": %d}'

        self.given_thing()
        self.given_state("reported", missing_config_state % 1)
        self.given_state("desired", missing_config_state % 2)

        self.when_getting_delta("reported", "desired")

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

        self.when_updating("reported", JSN % 1)

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

    def when_updating(self, state, value):
        self.db.update(THING, state, json.loads(value)) 

    def when_getting_delta(self, from_state, to_state):
        self.delta = self.db.get_delta(THING, from_state, to_state)  
    def when_getting_reported_desired_delta(self, base_state_supplement, reported_substitution, desired_substitution):
        state = FORMAT % BASE_STATE % base_state_supplement

        self.given_thing()
        self.given_state("reported", state % reported_substitution)
        self.given_state("desired", state % desired_substitution)

        self.when_getting_delta("reported", "desired")

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
            contents = json.loads(f.read())

        self.assertEqual(contents['state'], json.loads(value))

    def then_has_timestamp(self, state):
        p = Path(self.db_location) / THING / state 
        p = p.with_suffix('.json')
        with p.open() as f:
            contents = json.loads(f.read())

        self.assertTrue(contents.get('timestamp_utc'))

    def then_updated_more_recently(self, newer_state, older_state):
        p = Path(self.db_location) / THING / newer_state
        p = p.with_suffix('.json')
        with p.open() as f:
            newer_timestamp = json.loads(f.read())['timestamp_utc']

        p = Path(self.db_location) / THING / older_state
        p = p.with_suffix('.json')
        with p.open() as f:
            older_timestamp = json.loads(f.read())['timestamp_utc']

        self.assertTrue(newer_timestamp > older_timestamp)

    def then_two_histories(self, state):
        p = Path(self.db_location) / THING / "history"
        histories = [x for x in p.iterdir() if x.match('%s*' % state)]

        self.assertEqual(len(histories), 2)

    def then_history_exists(self, state, value, year = date.today().year):
        p = Path(self.db_location) / THING / "history" / state 
        p = p.with_suffix('.%d.txt' % year)
        with p.open() as f:
            self.assertEqual(f.read().strip(), value)

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
