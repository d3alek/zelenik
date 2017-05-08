import unittest
import state_processor
import json

ACTIONS = '{"actions": %s}'
SENSES = '{"senses": %s}'

class TestStateProcessor(unittest.TestCase):
    def test_explode_identity(self):
        simple = '{"value": "1"}'

        self.when_exploding(simple)

        self.then_exploded(simple)

    def test_explode_action(self):
        compact = ACTIONS % '{"A|sense|1H":["10~2"]}'
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "write": "high", "threshold": 10, "delta": 2, "delete": "no"}]}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_action_multiple(self):
        compact = ACTIONS % '{"A|sense|1H":["10~2", "2~3"]}'
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "write": "high", "threshold": 10, "delta": 2, "delete": "no"}, {"gpio": 1, "write": "high", "threshold": 2, "delta": 3, "delete": "no"}]}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_action_multiple_different_output(self):
        compact = ACTIONS % '{"A|sense|1H":["10~2"], "A|sense|2H":["10~2"]}'
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "write": "high", "threshold": 10, "delta": 2, "delete": "no"}, {"gpio": 2, "write": "high", "threshold": 10, "delta": 2, "delete": "no"}]}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_action_defaults_high(self):
        compact = ACTIONS % '{"A|sense|1": ["10~2"]}'
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "write": "high", "threshold": 10, "delta": 2, "delete": "no"}]}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_action_low(self):
        compact = ACTIONS % '{"A|sense|1L": ["10~2"]}'
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "write": "low", "threshold": 10, "delta": 2, "delete": "no"}]}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_action_identity(self):
        compact = ACTIONS % '{"A|sense|1L": ["10~2"]}'

        self.when_exploding(compact)
        self.when_compacting(json.dumps(self.exploded))

        self.then_compact(compact)

    def test_compact_action_writes_delete(self):
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "write": "low", "threshold": 10, "delta": 2, "delete": "yes"}]}'
        compact = ACTIONS % '{"A|sense|1L": ["10~-2"]}'

        self.when_compacting(exploded)

        self.then_compact(compact)

    def test_compact_action_multiple_different_gpios(self):
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "write": "low", "threshold": 10, "delta": 2, "delete": "yes"}, {"gpio": 2, "write": "low", "threshold": 10, "delta": 2, "delete": "yes"}]}'
        compact = ACTIONS % '{"A|sense|1L": ["10~-2"], "A|sense|2L": ["10~-2"]}'

        self.when_compacting(exploded)

        self.then_compact(compact)



    def test_compact_action_assumes_defaults(self):
        exploded = ACTIONS % '{"sense": [{"gpio": 1, "threshold": 10}]}'
        compact = ACTIONS % '{"A|sense|1H": ["10~0"]}'

        self.when_compacting(exploded)

        self.then_compact(compact)

    def test_explode_action_seconds(self):
        seconds_from_midnight = 41100 # 11:25:00 UTC
        one_hour = 3600 
        compact = ACTIONS % '{"A|time|1H": ["%d~%d"]}' % (seconds_from_midnight, one_hour)
        exploded = ACTIONS % '{"time": [{"gpio": 1, "write": "high", "threshold": "11:25", "delta": "1:00", "delete": "no"}]}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_action_seconds(self):
        seconds_from_midnight = 41100 # 11:25:00 UTC
        one_hour = 3600 
        exploded = ACTIONS % '{"time": [{"gpio": 1, "write": "high", "threshold": "11:25", "delta": "1:00", "delete": "no"}]}'
        compact = ACTIONS % '{"A|time|1H": ["%d~%d"]}' % (seconds_from_midnight, one_hour)

        self.when_compacting(exploded)

        self.then_compact(compact)

    def test_explode_capacitive_humidity_no_alias(self):
        compact = SENSES % '{"I2C-32c": 300}'
        exploded = SENSES % '{"I2C-32c": {"original": 300, "value": 0}}'

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

    def when_exploding(self, json_string):
        self.exploded = state_processor.explode(json.loads(json_string))

    def when_compacting(self, json_string):
        self.compact = state_processor.compact(json.loads(json_string))

    def then_exploded(self, expected_json_string):
        self.assertEqual(self.exploded, json.loads(expected_json_string))

    def then_compact(self, expected_json_string):
        self.assertEqual(self.compact, json.loads(expected_json_string))


if __name__ == '__main__':
    unittest.main()
