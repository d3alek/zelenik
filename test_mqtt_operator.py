import unittest
from pathlib import Path
import mqtt_operator
from tempfile import TemporaryDirectory
from datetime import date
from zipfile import ZipFile
import json

THING = "ESP-318885"
BASE_STATE = '{"state": %s}'

class TestMqttOperator(unittest.TestCase):
    def setUp(self):
        self.tmp_directory = TemporaryDirectory()
        self.db_directory = Path(self.tmp_directory.name) / 'db'
        self.db_directory.mkdir()
        self.operator = mqtt_operator.MqttOperator(self.tmp_directory.name)

    def tearDown(self):
        self.tmp_directory.cleanup()

    def test_safely_log_non_json(self):
        self.given_message('non-json', 'non-json')

        self.then_answer_is(mqtt_operator.OPERATOR_ERROR_TOPIC,
                mqtt_operator.MESSAGE_NOT_JSON)

    def test_parse_thing_action_failure(self):
        self.given_message('unknown', '{}')

        self.then_parsed_thing_action_are('', '')
        
    def test_parse_thing_action_success(self):
        action = "action"
        self.given_message('things/%s/%s' % (THING, action), '{}')

        self.then_parsed_thing_action_are(THING, action)

    def test_unknown_topic1(self):
        self.given_message('unknown', '{}')

        self.then_answer_is(mqtt_operator.OPERATOR_ERROR_TOPIC,
                mqtt_operator.MESSAGE_NOT_HANDLED)

    def test_unknown_topic2(self):
        self.given_message('things/ESP-12/exterminate', '{}')

        self.then_answer_is(mqtt_operator.OPERATOR_ERROR_TOPIC,
                mqtt_operator.MESSAGE_NOT_HANDLED)

    def test_wrong_format(self):
        self.given_message('things/%s/update' % THING, 
                '{"reported": {"value": 1}}') # missing outermost object 'state'

        self.then_parsed_thing_action_are(THING, "update")
        self.then_answer_is(mqtt_operator.OPERATOR_ERROR_TOPIC, 
                mqtt_operator.WRONG_FORMAT_STATE)
        self.then_state_does_not_exist("reported")

    def test_create_reported(self):
        self.given_message('things/%s/update' % THING, 
                BASE_STATE % '{"reported": {"value": 1}}')

        self.then_parsed_thing_action_are(THING, "update")
        self.then_answer_is('', '')
        self.then_state_exists("reported", '{"value": 1}')

    def given_message(self, topic, payload):
        self.message = (topic, payload)

    def then_parsed_thing_action_are(self, expected_thing, expected_action):
        topic, _ = self.message
        thing, action = mqtt_operator.parse_thing_action(topic)
        self.assertEqual(thing, expected_thing)
        self.assertEqual(action, expected_action)

    def then_answer_is(self, expected_answer_topic, expected_answer_payload):
        topic, payload = self.message
        answer_topic, answer_payload = self.operator.get_answer(topic, payload)
        self.assertEqual(answer_topic, expected_answer_topic)
        self.assertEqual(answer_payload, expected_answer_payload)

    def then_state_does_not_exist(self, state):
        p = self.db_directory / THING / state 
        p = p.with_suffix('.json')
        self.assertFalse(p.exists())

    def then_state_exists(self, state, expected_value, thing=THING):
        p = self.db_directory / thing / state 
        p = p.with_suffix('.json')
        with p.open() as f:
            contents = f.read()

        value = json.loads(contents)['state']
        self.assertEqual(value, json.loads(expected_value))

if __name__ == '__main__':
    unittest.main()
