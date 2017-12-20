import unittest
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta
import json

from pathlib import Path
import sys
root_path = Path(__file__).parent.parent
source_path = root_path / "src"

sys.path.append(str(root_path.absolute()))
sys.path.append(str(source_path.absolute()))
import zelenik_rest
import db_driver

def thing(index):
    return "thing-%d" % index

def now():
    return datetime.utcnow()

def sense(index):
    return "sense(%s)" % index

def write(index):
    return "write(%s)" % index

def to_string(sense):
    if sense is None:
        return ""
    else:
        return str(sense)

class ZelenikRestTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = TemporaryDirectory()
        self.temp_directory_path = Path(self.temp_directory.name)
        zelenik_rest.app.testing = True
        zelenik_rest.app.config["DATABASE"] = self.temp_directory_path
        self.app = zelenik_rest.app.test_client()

        db_driver.prepare_test_directory(self.temp_directory_path)
        self.db = db_driver.DatabaseDriver(working_directory=self.temp_directory.name)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_empty_history(self):
        self.given_thing(thing(1))
        rv = self.app.get("/db/%s/history?since_days=1" % thing(1))
        self.assertEqual(b'\r\n', rv.data)

    def test_simple(self):
        self.given_thing(thing(1))
        self.given_reported(thing(1),
                {'s' : {"value": 1}}, 
                {'w' : 0}, 
                now())

        self.when_getting("/db/%s/history?since_days=1" % thing(1))

        self.then_result(
                ("timestamp_utc", sense('s'), write('w')), 
                (now(), 1, 0))

    def test_aliased(self):
        self.given_thing(thing(1))
        self.given_reported(thing(1),
                {'s' : {"value": 1}}, 
                {'w' : 0}, 
                now())

        self.when_getting("/na/%s/history?since_days=1" % thing(1))

        self.then_result(
                ("timestamp_utc", sense('s'), write('w')), 
                (now(), 1, 0))

    def test_many_values(self):
        self.given_thing(thing(1))
        n = now()
        a_minute_ago = n - timedelta(minutes=1)
        self.given_reported(thing(1),
                {'s' : {"value": 1}}, 
                {}, 
                a_minute_ago)
        self.given_reported(thing(1),
                {'s' : {"value": 2}}, 
                {}, 
                n)

        self.when_getting("/db/%s/history?since_days=1" % thing(1))

        self.then_result(
                ("timestamp_utc", sense('s')), 
                (a_minute_ago, 1),
                (now(), 2)
                )

    def test_many_senses(self):
        self.given_thing(thing(1))
        self.given_reported(thing(1),
                {'s1' : {"value": 1},
                 's2' : {"value": 2}}, 
                {}, 
                now())

        self.when_getting("/db/%s/history?since_days=1" % thing(1))

        self.then_result(
                ("timestamp_utc", sense('s1'), sense('s2')), 
                (now(), 1, 2)
                )

    def test_missing_senses(self):
        self.given_thing(thing(1))

        n = now()
        a_minute_ago = n - timedelta(minutes=1)
        self.given_reported(thing(1),
                {'s1' : {"value": 1}}, 
                {}, 
                a_minute_ago)
        self.given_reported(thing(1),
                {'s2' : {"value": 2}}, 
                {}, 
                n)

        self.when_getting("/db/%s/history?since_days=1" % thing(1))

        self.then_result(
                ("timestamp_utc", sense('s1'), sense('s2')), 
                (a_minute_ago, 1, None),
                (n, None, 2)
                )

    def given_thing(self, thing):
        self.db._prepare_directory(self.db.directory / thing)

    def given_reported(self, thing, senses, writes, time):
        state = { "senses": senses }
        state["write"] = writes
        self.db._update_reported(thing, state, time)

    def when_getting(self, url):
        self.response = self.app.get(url)

    def then_result(self, *lines):
        string = ",".join(lines[0])
        string += "\r\n"
        string += "\r\n".join([db_driver.timestamp(line[0]) + "," +  ",".join([to_string(sense) for sense in line[1:]]) for line in lines[1:]])
        string += "\r\n"
        self.assertEqual(bytes(string, encoding="utf-8"), self.response.data)


if __name__ == "__main__":
    unittest.main()




