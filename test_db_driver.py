import unittest
from pathlib import Path
import db_driver
from tempfile import TemporaryDirectory
from datetime import date, datetime, timedelta
from zipfile import ZipFile, ZIP_DEFLATED
import json
import state_processor

THING="thing"
BASE_STATE = '{"config": %s}'
FORMAT = '{"state": %s, "timestamp_utc": "2017-01-25 15:34:12.989202"}'
JSN = '{"value": "%s"}' # separate case from BASE_STATE for convenience - notice the " surrounding %s
FORMAT_TS = '{"state": %s, "timestamp_utc": "%s"}'
DISP = '{"alias":"","color":"green","position":"0,0","type":"number","plot":"yes","graph":"yes"}'
ALIASED_DISP = '{"alias":"%s","color":"green","position":"0,0","type":"number","plot":"yes","graph":"yes"}'
COLORED_DISP = '{"alias":"","color":"%s","position":"0,0","type":"number","plot":"yes","graph":"yes"}'

# source http://stackoverflow.com/a/765990
def years_ago(years, from_date):
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        # Must be 2/29!
        assert from_date.month == 2 and from_date.day == 29 # can be removed
        return from_date.replace(month=2, day=28,
                                 year=from_date.year-years)

def timeless(d):
    dc = d.copy()
    if dc.get('timestamp_utc'):
        dc.pop('timestamp_utc') 
    return dc


class TestDatabaseDriver(unittest.TestCase):
    def setUp(self):
        self.temp_directory = TemporaryDirectory()
        self.temp_directory_path = Path(self.temp_directory.name)
        self.db_directory = self.temp_directory_path / "db"
        self.db_directory.mkdir()

        self.view_directory = self.temp_directory_path / "view"
        view_location = self.view_directory.name
        self.view_directory.mkdir()
        index = self.view_directory  / "index.html"
        index.touch()
        style = self.view_directory / "style.html"
        style.touch()

        self.db = db_driver.DatabaseDriver(working_directory=self.temp_directory.name)

    def tearDown(self):
        self.temp_directory.cleanup()

    def given_thing(self):
        p = self.db_directory / THING
        p.mkdir()

    def given_aliased_thing(self, alias):
        p = self.db_directory / "na"
        if not p.is_dir():
            p.mkdir()

        p = p / alias 
        p.symlink_to(self.db_directory / THING)

    def given_state(self, state, value):
        p = self.db_directory / THING / state
        p = p.with_suffix('.json')
        with p.open('w') as f:
            f.write(value)

    def when_updating_reported(self, value):
        self.db.update_reported(THING, json.loads(value)) 

    def when_updating_desired(self, value, thing = THING):
        self.db.update_desired(thing, json.loads(value)) 

    def when_getting_delta(self):
        self.delta = self.db.get_delta(THING)  

    def then_state_exists(self, state, value):
        p = self.db_directory / THING / state 
        p = p.with_suffix('.json')
        with p.open() as f:
            contents = timeless(json.loads(f.read()))

        expected_value = timeless(json.loads(value))
        self.assertEqual(contents, expected_value)

    def then_delta_is(self, delta_string):
        self.assertEqual(self.delta, json.loads(delta_string))

class TestDatabaseDriverUpdate(TestDatabaseDriver):
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

    def test_update_reported_preserves_desired(self):
        self.given_thing()
        self.given_state("reported", FORMAT % BASE_STATE % JSN % 1)
        self.given_state("desired", JSN % 1)

        self.when_updating_desired(JSN % 2)
        self.when_updating_reported(BASE_STATE % JSN % 1)

        self.then_state_exists("desired", JSN % 2)

    def test_update_desired_action_fills_missing_fields(self):
        self.given_thing()
        actions_wrapper = '{"actions":%s}'
        incomplete_action = '{"sense":{"gpio": 1, "threshold": 10}}'
        complete_action = '{"sense":{"gpio": 1, "threshold": 10, "delta": 0, "delete": "no", "write": "high"}}'

        self.when_updating_desired(actions_wrapper % incomplete_action)

        self.then_state_exists("desired", actions_wrapper % complete_action)

    def test_first_reported_creates_displayables(self):
        self.given_thing()

        self.when_updating_reported(BASE_STATE % '{"1": 0}')

        displayables = '{"1":%s}' % DISP
        self.then_state_exists("displayables", displayables) 

    def test_update_reported_updates_displayables(self):
        self.given_thing()
        self.given_state("reported", FORMAT % BASE_STATE % '{"a":1}')
        self.given_state("displayables", '{"a":%s}' % DISP)

        self.when_updating_reported(BASE_STATE % '{"a": 1, "c": 2}')
        self.then_state_exists("displayables", '{"a":%s,"c":%s}' % (COLORED_DISP % 'green', COLORED_DISP % 'red'))

    def test_update_reported_adds_timestamp(self):
        self.given_thing()

        self.when_updating_reported(JSN % 1)

        self.then_has_timestamp("reported")

    def test_update_updates_state(self):
        self.given_thing()
        self.given_state("reported", FORMAT % JSN % 1)

        self.when_updating_reported(JSN % 2)

        self.then_state_exists("reported", FORMAT % JSN % 2)

    def test_update_reported_deletes_graph(self):
        self.given_thing()
        self.given_state("reported", BASE_STATE % '{}')
        self.given_graph()
        self.given_weekly_graph()

        self.when_updating_reported(JSN % 1)

        self.then_no_graph()

    def test_update_reported_includes_alias(self):
        self.given_thing()
        self.given_alias("value", "temperature")
        self.given_state("reported", BASE_STATE % '{}') # necessary otherwise next command will override displayables

        self.when_updating_reported(JSN % "a")

        self.then_state_exists("reported", FORMAT % ('{"value": {"value": "a", "alias": "temperature"}}'))

    def test_update_desired_resolves_alias(self):
        aliased_thing = "aliased-%s" % THING
        self.given_thing()
        self.given_aliased_thing(aliased_thing)

        self.when_updating_desired(JSN % 1, thing=aliased_thing)

        self.then_state_exists("desired", JSN % 1)

    def given_graph(self):
        p = self.db_directory / THING / "graph.png"
        p.touch()

    def given_weekly_graph(self):
        p = self.db_directory / THING / "graph-7.png"
        p.touch()

    def given_alias(self, key, value):
        p = self.db_directory / THING / "displayables.json"
        
        aliased = json.loads(ALIASED_DISP % value)
        with p.open('w') as f:
            f.write(json.dumps({key : aliased}))

    def then_no_graph(self):
        p = self.db_directory / THING / "graph.png"
        self.assertFalse(p.exists())

        p = self.db_directory / THING / "graph-7.png"
        self.assertFalse(p.exists())

        p = self.db_directory / THING / "graph-31.png"
        self.assertFalse(p.exists())

        p = self.db_directory / THING / "graph-366.png"
        self.assertFalse(p.exists())

    def then_one_thing(self):
        p = self.db_directory
        things = [x for x in p.iterdir()]
        self.assertEqual(len(things), 1)

    def then_thing_exists(self):
        p = self.db_directory / THING
        self.assertTrue(p.exists())

    def then_thing_has_view(self):
        p = self.db_directory / THING / "index.html"
        self.assertTrue(p.exists())

    def then_has_timestamp(self, state):
        p = self.db_directory / THING / state 
        p = p.with_suffix('.json')
        with p.open() as f:
            contents = json.loads(f.read())

        self.assertTrue(contents.get('timestamp_utc'))


class TestDatabaseDriverGetDelta(TestDatabaseDriver): 
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

    def test_get_delta_ignores_aliases(self):
        base = '{"1":%s}'
        self.when_getting_reported_desired_delta(base, '{"alias":"a", "value": 1}', 1)

        self.then_delta_is('{}')

    def when_getting_reported_desired_delta(self, base_state_supplement, reported_substitution, desired_substitution):
        state_reported = FORMAT % BASE_STATE % base_state_supplement
        state_desired = base_state_supplement

        self.given_thing()
        self.given_state("reported", state_reported % reported_substitution)
        self.given_state("desired", state_desired % desired_substitution)

        self.when_getting_delta()


class TestDatabaseDriverHistory(TestDatabaseDriver): 
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

    def test_update_archives_history_from_two_days_ago(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        self.given_thing()
        self.given_state("reported", JSN % "old")
        self.given_history("reported", JSN % "oldest", day=two_days_ago)
        self.given_history("reported", JSN % "older", day=yesterday)
        self.when_updating_reported(JSN % "new")

        self.then_two_histories("reported")
        self.then_history_exists("reported", JSN % "older", day=yesterday)
        self.then_history_exists("reported", JSN % "old")
        self.then_archive_exists("reported", JSN % "oldest", until=two_days_ago)
        self.then_state_exists("reported", FORMAT % JSN % "new")

    # necessary for states do not change every day 
    # or for the case that a devices has been offline
    def test_update_archives_history_older_than_yesterday(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        last_week = today - timedelta(days=7)

        self.given_thing()
        self.given_state("reported", JSN % "old")
        self.given_history("reported", JSN % "oldest", day=last_week)
        self.given_history("reported", JSN % "older", day=yesterday)
        self.when_updating_reported(JSN % "new")

        self.then_two_histories("reported")
        self.then_history_exists("reported", JSN % "older", day=yesterday)
        self.then_history_exists("reported", JSN % "old")
        self.then_archive_exists("reported", JSN % "oldest", until=last_week)
        self.then_state_exists("reported", FORMAT % JSN % "new")

    def test_update_appends_to_archive(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        three_days_ago = today - timedelta(days=3)

        self.given_thing()
        self.given_state("reported", JSN % "old")
        self.given_history("reported", JSN % "oldest", day=two_days_ago)
        self.given_history("reported", JSN % "older", day=yesterday)
        self.given_archive("reported", JSN % "archive", until=three_days_ago)

        self.when_updating_reported(JSN % "new")

        self.then_archive_exists("reported", "%s\n%s" % (JSN % "archive", JSN % "oldest"), until=two_days_ago)

    def test_first_archive_for_new_year_marks_last_year_complete(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        a_day_last_year = years_ago(1, today)

        self.given_thing()
        self.given_state("reported", JSN % "old")
        self.given_history("reported", JSN % "new year", day=two_days_ago)
        self.given_history("reported", JSN % "older", day=yesterday)
        self.given_archive("reported", JSN % "archived", until=a_day_last_year)

        self.when_updating_reported(JSN % "new")

        self.then_archive_exists("reported", JSN % "archived", until=a_day_last_year, complete=True)
        self.then_archive_exists("reported", JSN % "new year", until=two_days_ago)
        self.then_state_exists("reported", FORMAT % JSN % "new")

    def list_directory(self, directory):
        d = self.db_directory / THING / directory
        print("%s:" % d)
        for x in d.iterdir():
            print(x)
        print("---")

    def test_load_history(self):
        today = date.today()
        yesterday = today - timedelta(days=1)

        today_timestamp = datetime.utcnow().isoformat(sep=' ')
        yesterday_timestamp = (datetime.utcnow() - timedelta(days=1)).isoformat(sep=' ')

        self.given_thing()

        self.given_state("reported", FORMAT_TS % (JSN % 3, today_timestamp))
        self.given_history("reported", FORMAT_TS % (JSN % 2, today_timestamp), day=today)
        self.given_history("reported", FORMAT_TS % (JSN % 1, yesterday_timestamp), day=yesterday)

        self.when_loading_reported_history()

        self.then_history_values_are([1, 2, 3])

    def test_load_history_since_days(self):
        today = datetime.utcnow().isoformat(sep=' ')
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat(sep=' ')

        self.given_thing()
        self.given_state("reported", FORMAT_TS % (JSN % 2, today))
        self.given_history("reported", FORMAT_TS % (JSN % 1, yesterday))

        self.when_loading_reported_history(since_days=1)

        self.then_history_values_are([2])

    def test_load_history_reads_from_archive(self):
        today = date.today()
        last_week = today - timedelta(days=7)

        today_timestamp = datetime.utcnow().isoformat(sep=' ')
        last_week_timestamp = (datetime.utcnow() - timedelta(days=7)).isoformat(sep=' ')

        self.given_thing()

        self.given_state("reported", FORMAT_TS % (JSN % 2, today_timestamp))
        self.given_archive("reported", FORMAT_TS % (JSN % 1, last_week_timestamp), until = last_week)

        self.list_directory("history/archive")

        self.when_loading_reported_history()

        self.then_history_values_are([1, 2])


    def test_update_desired_adds_history_timestamp(self):
        self.given_thing()
        self.given_state("desired", JSN % 1)

        self.when_updating_desired(JSN % 2)

        self.then_history_has_timestamp("desired")

    def given_history(self, state, value, day=date.today()):
        p = self.db_directory / THING / "history"
        if not p.is_dir():
            p.mkdir()
        p = p / state
        p = p.with_suffix('.%s.txt' % day.isoformat())
        with p.open('w') as f:
            f.write(value)
            f.write('\n')

    def given_archive(self, state, value, until, complete=False):
        p = self.db_directory / THING / "history" / "archive"
        if not p.is_dir():
            p.mkdir(parents=True)
        p = p / state
        if complete:
            suffix = '%d' % until.year
        else:
            suffix = 'until-%s' % until.isoformat()

        p = p.with_suffix('.%s.zip' % suffix)

        with ZipFile(str(p), 'w', ZIP_DEFLATED) as zf:
            arcname = '%s.%s.txt' % (state, suffix)
            zf.writestr(arcname, value + '\n')

    def when_loading_reported_history(self, since_days=366):
        self.history = self.db.load_history(THING, 'reported', since_days=since_days)

    def then_history_has_timestamp(self, state):
        p = self.db_directory / THING / 'history' / state 
        p = p.with_suffix('.%s.txt' % date.today().isoformat())
        with p.open() as f:
            contents = json.loads(f.read())

        self.assertTrue(contents.get('timestamp_utc'))

    def then_two_histories(self, state):
        p = self.db_directory / THING / "history"
        histories = [x for x in p.iterdir() if x.match('%s*' % state)]
        self.assertEqual(len(histories), 2)

    def then_history_exists(self, state, value, day = date.today()):
        p = self.db_directory / THING / "history" / state 
        p = p.with_suffix('.%s.txt' % day.isoformat())
        with p.open() as f:
            lines = f.readlines()
            actual = [timeless(json.loads(line)) for line in lines]
        values = value.split('\n')
        expected = [timeless(json.loads(value)) for value in values]
        self.assertEqual(actual, expected)

    def then_archive_exists(self, state, value, until, complete=False):
        p = self.db_directory / THING / "history" / "archive" / state 
        if complete:
            suffix = '%d' % until.year
        else:
            suffix = 'until-%s' % until.isoformat()

        p = p.with_suffix(".%s.zip" % suffix)
        with ZipFile(str(p)) as zf:
            file_name = zf.namelist()[0]
            byte_text = zf.read(file_name)
            text = byte_text.decode('utf-8')
            self.assertEqual(text.strip(), value)

    def then_history_values_are(self, values):
        actual_values = list(map(lambda s: int(s['state']['value']), self.history))
        self.assertEqual(actual_values, values)

class TestDatabaseDriverStateProcessor(TestDatabaseDriver):
    def test_update_action_prettifies(self):
        action = '{"actions": {"A|sense|10H":"21~1"}}'
        exploded_action = json.dumps(state_processor.explode(json.loads(action)))

        self.when_updating_reported(action)

        self.then_state_exists("reported", FORMAT % exploded_action )

    def test_get_delta_compacts(self):
        compact_from = '{"actions":{"A|I2C-9|4L":"5~1"}}'
        compact_to = '{"actions":{"A|I2C-9|4H":"5~1"}}'
        exploded_from = json.dumps(state_processor.explode(json.loads(compact_from)))
        exploded_to = json.dumps(state_processor.explode(json.loads(compact_to)))
        state_reported = FORMAT % BASE_STATE % exploded_from
        state_desired = exploded_to

        self.given_thing()
        self.given_state("reported", state_reported)
        self.given_state("desired", state_desired)

        self.when_getting_delta()

        self.then_delta_is(compact_to)

class TestDatabaseDriverThingAlias(TestDatabaseDriver):
    def test_update_thing_alias_deletes_old_alias(self):
        old_aliased_thing = "old-aliased-%s" % THING
        new_aliased_thing = "new-aliased-%s" % THING

        reported = FORMAT % BASE_STATE % JSN % 1
        self.given_thing()
        self.given_state("reported", reported)

        self.given_aliased_thing(old_aliased_thing)

        self.when_updating_thing_alias(new_aliased_thing) 

        self.then_thing_alias_exists(new_aliased_thing)
        self.then_thing_alias_does_not_exist(old_aliased_thing)

    def when_updating_thing_alias(self, alias):
        self.db.update_thing_alias(THING, alias)

    def then_thing_alias_exists(self, alias):
        p = self.db_directory / "na" / alias 
        self.assertTrue(p.is_symlink())

    def then_thing_alias_does_not_exist(self, alias):
        p = self.db_directory / "na" / alias 
        self.assertFalse(p.is_symlink())

if __name__ == '__main__':
    unittest.main()
