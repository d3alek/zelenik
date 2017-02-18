import unittest
import state_processor
import json

ACTIONS = '{"actions": %s}'

class TestStateProcessor(unittest.TestCase):
    def test_explode_identity(self):
        simple = '{"value": "1"}'

        self.when_exploding(simple)

        self.then_exploded(simple)

    def test_explode_action(self):
        compact = ACTIONS % '{"A|sense|1H": "10~2"}'
        exploded = ACTIONS % '{"sense": {"gpio": 1, "write": "high", "threshold": 10, "delta": 2}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_action_defaults_high(self):
        compact = ACTIONS % '{"A|sense|1": "10~2"}'
        exploded = ACTIONS % '{"sense": {"gpio": 1, "write": "high", "threshold": 10, "delta": 2}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_explode_action_low(self):
        compact = ACTIONS % '{"A|sense|1L": "10~2"}'
        exploded = ACTIONS % '{"sense": {"gpio": 1, "write": "low", "threshold": 10, "delta": 2}}'

        self.when_exploding(compact)

        self.then_exploded(exploded)

    def test_compact_action_identity(self):
        compact = ACTIONS % '{"A|sense|1L": "10~2"}'

        self.when_exploding(compact)
        self.when_compacting(json.dumps(self.exploded))

        self.then_compact(compact)

    def test_explode_action_adds_delete(self):
        self.fail()

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
