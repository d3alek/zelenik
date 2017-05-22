import unittest
import state_processor
import json

ACTIONS = '{"actions": %s}'
SENSES = '{"senses": %s}'

def action(sense, gpio, write, threshold, delta): 
    return json.dumps(state_processor.action(sense, gpio, write, threshold, delta))

class TestStateProcessor(unittest.TestCase):
    def test_explode_identity(self):
        simple = '{"value": "1"}'

        self.when_exploding(simple)

        self.then_exploded(simple)

    def test_explode_action(self):
        compact = ACTIONS % '["sense|1|H|10|2"]'
        exploded = ACTIONS % '[%s]' % action('sense', 1, 'high', 10, 2)

        self.when_exploding(compact)

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
        exploded = SENSES % '{"I2C-8": {"original": 800, "value": 100}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_resistive_humidity_action(self):
        exploded = ACTIONS % '[{"sense":"I2C-8", "threshold": 100, "gpio": 0}]'
        compact = ACTIONS % '["I2C-8|0|H|800|0"]'

        self.when_compacting(exploded)

        self.then_compact(compact)

    def test_explode_resistive_humidity_action(self):
        compact = ACTIONS % '["I2C-8|0|H|800|0"]'
        exploded = ACTIONS % '[{"sense":"I2C-8", "threshold": 100, "gpio": 0, "delta": 0, "write": "high"}]'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_capacitive_humidity_no_alias(self):
        compact = SENSES % '{"I2C-32c": 300}'
        exploded = SENSES % '{"I2C-32c": {"original": 300, "value": 0}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_resistive_humidity_with_alias(self):
        compact = SENSES % '{"I2C-8": {"alias": "a", "value": 800}}'
        exploded = SENSES % '{"I2C-8": {"alias": "a", "original": 800, "value": 100}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_capacitive_humidity_with_alias(self):
        compact = SENSES % '{"I2C-32c": {"alias": "a", "value": 300}}'
        exploded = SENSES % '{"I2C-32c": {"alias": "a", "original": 300, "value": 0}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_capacitive_max(self):
        compact = SENSES % '{"I2C-32c": {"alias": "a", "value": 800}}'
        exploded = SENSES % '{"I2C-32c": {"alias": "a", "original": 800, "value": 100}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_wrong_sense_removes_value(self):
        compact = SENSES % '{"I2C-8": {"alias": "a", "value": "w0"}}'
        exploded = SENSES % '{"I2C-8": {"alias": "a", "wrong": "w0"}}'
        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_wrong_sense_does_nothing(self):
        exploded = SENSES % '{"I2C-8": {"alias": "a", "value": "w0"}}'
        self.when_compacting(exploded)

        self.then_compact(exploded)

    def test_explode_wrong_value_picks_previous_good(self):
        compact = SENSES % '{"I2C-8": "w800"}'
        previous_exploded = SENSES % '{"I2C-8": {"original": 500, "value": 30}, "timestamp_utc": "yesterday"}'
        exploded = SENSES % '{"I2C-8": {"wrong": "w800", "value": 30, "from": "yesterday"}}'
    def test_explode_wrong_value_picks_previous_good_and_timestamp(self):
        compact = SENSES % '{"I2C-8": "w700"}'
        previous_exploded = SENSES % '{"I2C-8": {"wrong": "w800", "original": 800, "value": 100, "from": "two-days-ago"}, "timestamp_utc": "yesterday"}'
        exploded = SENSES % '{"I2C-8": {"wrong": "w700", "original": 800, "value": 100, "from": "two-days-ago"}}'

        self.when_exploding(compact, previous_exploded)

        self.then_exploded(exploded)

    def when_exploding(self, json_string, previous = "{}"):
        self.exploded = state_processor.explode(json.loads(json_string), json.loads(previous))

    def when_compacting(self, json_string):
        self.compact = state_processor.compact(json.loads(json_string))

    def then_exploded(self, expected_json_string):
        self.assertEqual(self.exploded, json.loads(expected_json_string))

    def then_compact(self, expected_json_string):
        self.assertEqual(self.compact, json.loads(expected_json_string))


if __name__ == '__main__':
    unittest.main()
