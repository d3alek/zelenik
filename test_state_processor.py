import unittest
import state_processor
import json
from state_processor import WRONG_VALUE_INT
from db_driver import timestamp
from datetime import datetime, timedelta

ACTIONS = '{"actions": %s}'
SENSES = '{"senses": %s}'

def action(sense, gpio, write, threshold, delta): 
    return json.dumps(state_processor.action(sense, gpio, write, threshold, delta))

def yesterday():
    return datetime.utcnow() - timedelta(days=1)

def two_hours_ago():
    return datetime.utcnow() - timedelta(hours=1)

class TestStateProcessor(unittest.TestCase):
    def test_explode_identity(self):
        simple = '{"value": "1"}'

        self.when_exploding(simple)

        self.then_exploded(simple)

    def test_explode_boot_time(self):
        compact = '{"b":1498465149}'
        exploded = '{"boot_utc": "2017-06-26 08:19:09"}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_preserve_boot_time_on_small_delta(self):
        compact = '{"b":1498465149}' # 2017-06-26 08:19:09
        exploded = '{"boot_utc": "2017-06-26 08:19:07"}'
        previous_exploded = '{"boot_utc": "2017-06-26 08:19:07", "timestamp_utc": "2017-06-26 08:18:00"}'

        self.when_exploding(compact, previous_exploded)

        self.then_exploded(exploded)

    def test_explode_fix_boot_time_on_previous_in_the_future(self):
        compact = '{"b":1498465149}'
        exploded = '{"boot_utc": "2017-06-26 08:19:09"}'
        previous_exploded = '{"boot_utc": "2117-06-26 08:17:00", "timestamp_utc": "2017-06-26 08:18:00"}'

        self.when_exploding(compact, previous_exploded)

        self.then_exploded(exploded)

    # TODO This test won't work as we are using datetime.utcnow() until we either start passing now or mock datetime
    #def test_preserve_boot_time_if_sleeping(self):
    #    compact = '{"b":1498465149}' # 2017-06-26 08:19:09
    #    exploded = '{"boot_utc": "2017-06-26 08:17:00"}'
    #    previous_exploded = '{"boot_utc": "2017-06-26 08:17:00", "config":{"sleep":60}, "timestamp_utc": "2017-06-26 08:18:00"}'

    #    self.when_exploding(compact, previous_exploded)

    #    self.then_exploded(exploded)

    def test_adjust_boot_time_if_overslept(self):
        compact = '{"b":1498465149}'
        exploded = '{"boot_utc": "2017-06-26 08:19:09"}'
        previous_exploded = '{"boot_utc": "2017-06-26 08:17:00", "config":{"sleep":60}, "timestamp_utc": "2017-06-26 08:17:00"}'

        self.when_exploding(compact, previous_exploded)

        self.then_exploded(exploded)

    def test_explode_action(self):
        compact = ACTIONS % '["sense|1|H|10|2"]'
        exploded = ACTIONS % '[%s]' % action('sense', 1, 'high', 10, 2)

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_already_exploded_action(self):
        exploded = ACTIONS % '[%s]' % action('sense', 1, 'high', 10, 2)
        exploded = ACTIONS % '[%s]' % action('sense', 1, 'high', 10, 2)

        self.when_exploding(exploded)

        self.then_exploded(exploded)

    def test_explode_action_multiple(self):
        compact = ACTIONS % '["sense|1|H|10|2", "sense|1|H|2|3"]'
        exploded = ACTIONS % '[%s, %s]' % (action('sense', 1, 'high', 10, 2), action('sense', 1, 'high', 2, 3))

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_action_low(self):
        compact = ACTIONS % '["sense|1|L|10|2"]'
        exploded = ACTIONS % '[%s]' % action('sense', 1, 'low', 10, 2)

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_action_identity(self):
        compact = ACTIONS % '["sense|1|L|10|2"]'

        self.when_exploding(compact)
        self.when_compacting(json.dumps(self.exploded))

        self.then_compact(compact)

    def test_compact_action_assumes_defaults(self):
        exploded = ACTIONS % '[{"sense": "sense", "gpio": 1, "threshold": 10}]'
        compact = ACTIONS % '["sense|1|H|10|0"]'

        self.when_compacting(exploded)

        self.then_compact(compact)

    def test_explode_action_seconds(self):
        seconds_from_midnight = 41100 # 11:25:00 UTC
        one_hour = 3600 
        compact = ACTIONS % '["time|1|H|%d|%d"]' % (seconds_from_midnight, one_hour)
        exploded = ACTIONS % "[%s]" % action('time', 1, 'high', '11:25', '1:00')

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_action_seconds(self):
        seconds_from_midnight = 41100 # 11:25:00 UTC
        one_hour = 3600 
        exploded = ACTIONS % "[%s]" % action('time', 1, 'high', '11:25', '1:00')
        compact = ACTIONS % '["time|1|H|%d|%d"]' % (seconds_from_midnight, one_hour)

        self.when_compacting(exploded)

        self.then_compact(compact)

    def test_explode_resistive_humidity(self):
        compact = SENSES % '{"I2C-8": 800}'
        exploded = SENSES % '{"I2C-8": {"value": 800}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_capacitive_humidity_no_alias(self):
        compact = SENSES % '{"I2C-32c": 300}'
        exploded = SENSES % '{"I2C-32c": {"value": 300}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_deprecated_sense(self):
        compact = SENSES % '{"OW-x": 20}'
        exploded = SENSES % '{"OW-x": {"value": 20}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_deprecated_sense_wrong(self):
        compact = SENSES % '{"OW-x": "w20"}'
        exploded = SENSES % '{"OW-x": {"wrong": 20}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_resistive_humidity_with_alias(self):
        compact = SENSES % '{"I2C-8": {"alias": "a", "value": 800}}'
        exploded = SENSES % '{"I2C-8": {"alias": "a", "value": 800}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_enriched_sense(self):
        compact = SENSES % '{"OW-x": "100|98|10|c"}'
        exploded = SENSES % '{"OW-x": {"value": 100, "expected": 98, "ssd": 10}}'
        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_float_enriched_sense(self):
        compact = SENSES % '{"OW-x": "10.5|98|10|c"}'
        exploded = SENSES % '{"OW-x": {"value": 10.5, "expected": 98, "ssd": 10}}'
        self.when_exploding(compact)

        self.then_exploded(exploded)



    def test_explode_wrong_sense_removes_value(self):
        compact = SENSES % '{"I2C-8": "100|800|10|w"}'
        exploded = SENSES % '{"I2C-8": {"wrong": 100, "expected": 800, "ssd": 10}}'
        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_wrong_sense_does_nothing(self):
        exploded = SENSES % '{"I2C-8": {"alias": "a", "value": "0|0|0|w"}}'
        self.when_compacting(exploded)

        self.then_compact(exploded)

    def test_explode_picks_missing_from_previous(self):
        compact = SENSES % '{"OW-x": "100|80|100|c"}'
        previous_exploded = SENSES % '{"OW-y": {"value": 80}}'
        exploded = SENSES % '{"OW-x": {"value": 100, "expected":80, "ssd":100}, "OW-y": {"value": 80, "from": "%s"}}' % timestamp(two_hours_ago())

        self.when_exploding(compact, previous_exploded, timestamp(two_hours_ago()))
        self.then_exploded(exploded)

    def test_explode_does_not_pick_missing_from_old_previous(self):
        compact = SENSES % '{"OW-x": "100|100|100|c"}'
        previous_exploded = SENSES % '{"OW-y": {"value": 80}}'
        exploded = SENSES % '{"OW-x": {"value": 100, "expected": 100, "ssd": 100}}'

        self.when_exploding(compact, previous_exploded, timestamp(yesterday()))
        self.then_exploded(exploded)

    def test_explode_does_not_pick_missing_from_old_sense(self):
        compact = SENSES % '{"OW-x": "100|100|100|c"}'
        previous_exploded = SENSES % '{"OW-y": {"value": 80, "from": "%s"}}' % timestamp(yesterday())
        exploded = SENSES % '{"OW-x": {"value": 100, "expected": 100, "ssd": 100}}'

        self.when_exploding(compact, previous_exploded, timestamp(two_hours_ago()))
        self.then_exploded(exploded)

    def test_explode_wrong_value_picks_expected(self):
        compact = SENSES % '{"I2C-8": "1000|800|100|w"}'
        previous_exploded = SENSES % '{"I2C-8": {"value": 800}}'
        exploded = SENSES % '{"I2C-8": {"wrong": 1000, "ssd":100, "expected": 800}}'

        self.when_exploding(compact, previous_exploded, "yesterday")
        self.then_exploded(exploded)

    def test_explode_wrong_no_expected_picks_previous_good(self):
        compact = SENSES % '{"I2C-8": "1000|%s|100|w"}' % WRONG_VALUE_INT
        previous_exploded = SENSES % '{"I2C-8": {"value": 800}}'
        exploded = SENSES % '{"I2C-8": {"wrong": 1000, "value":800, "ssd": 100, "from": "yesterday"}}'

        self.when_exploding(compact, previous_exploded, "yesterday")
        self.then_exploded(exploded)

    def test_explode_wrong_value_picks_previous_good_and_timestamp(self):
        compact = SENSES % '{"I2C-8": "700|%s|100|w"}' % WRONG_VALUE_INT
        previous_exploded = SENSES % '{"I2C-8": {"wrong": 1000, "value": 800, "from": "two-days-ago"}, "timestamp_utc": "yesterday"}'
        exploded = SENSES % '{"I2C-8": {"wrong": 700, "value": 800,"ssd": 100, "from": "two-days-ago"}}'

        self.when_exploding(compact, previous_exploded)

        self.then_exploded(exploded)

    def when_exploding(self, json_string, previous = "{}", previous_timestamp = None):
        self.exploded = state_processor.explode(json.loads(json_string), json.loads(previous), previous_timestamp)

    def when_compacting(self, json_string):
        self.compact = state_processor.compact(json.loads(json_string))

    def then_exploded(self, expected_json_string):
        self.assertEqual(self.exploded, json.loads(expected_json_string))

    def then_compact(self, expected_json_string):
        self.assertEqual(self.compact, json.loads(expected_json_string))


if __name__ == '__main__':
    unittest.main()
