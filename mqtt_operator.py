#!/www/zelenik/venv/bin/python

import paho.mqtt.client as mqtt
import db_driver
import json
import re
import time

from db_driver import to_compact_json

from logger import Logger
logger = Logger("mqtt_operator")

ERROR_TOPIC = "operator_error"
MESSAGE_NOT_HANDLED = '{"reason": "Message not handled. See mqtt_operator logs for details"}'
MESSAGE_NOT_JSON = '{"reason": "Message not a valid json. See mqtt_operator logs for details"}'
WRONG_FORMAT_STATE = '{"reason": "Message payload did not begin with state object. See mqtt_operator logs for details"}'
WRONG_FORMAT_REPORTED_DESIRED = '{"reason": "Message payload did not begin with state/reported or state/desired objects. See mqtt_operator logs for details"}'
UPDATE_REPORTED_EXCEPTION = '{"reason": "Caught exception while updating reported: %s. See mqtt_operator logs for details"}'

DIR = '/www/zelenik/'

def add_time(d):
    d['t'] = int(time.time()) # seconds since EPOCH, Posix time

def parse_username_password():
    with open(DIR + 'secret/mqtt_password_file') as f:
        contents = f.read()
    username, _ = contents.split(':')

    with open(DIR + 'secret/mqtt_password') as f:
        password = f.read()

    return username.strip(), password.strip()

def parse_thing_action(topic):
    match = re.match(r'things\/([a-zA-Z0-9-]+)\/(\w+)', topic)
    log = logger.of("parse_thing_action")
    if not match:
        log.info("Could not parse thing and action from topic %s" % topic)
        return "", ""
    thing = match.group(1)
    action = match.group(2)
    return thing, action

def get_answer(db, topic, payload_string):

    log = logger.of("get_answer")

    try:
        payload = json.loads(payload_string)
    except ValueError:
        log.error("Payload is not a valid json. %s - %s" % (topic, payload_string), traceback=True)
        answer_topic = ERROR_TOPIC
        answer_payload = MESSAGE_NOT_JSON
        return answer_topic, answer_payload

    thing, action = parse_thing_action(topic)

    if action == "update":
        if not payload.get("state"):
            log.error("Update payload does not begin with a state object. %s - %s" % (topic, payload))
            answer_topic = ERROR_TOPIC
            answer_payload = WRONG_FORMAT_STATE
            return answer_topic, answer_payload

        if payload["state"].get("reported"): # these come from things
            try:
                db.update('reported', thing, payload["state"]["reported"])
            except Exception:
                log.error("Updating reported failed with an exception.", traceback=True)
                e = sys.exc_info()[0]
                answer_topic = ERROR_TOPIC
                answer_payload = UPDATE_REPORTED_EXCEPTION % e

                return answer_topic, answer_payload
        else:
            log.error("Update does not contain reported. %s - %s" % (topic, payload))
            answer_topic = ERROR_TOPIC
            answer_payload = WRONG_FORMAT_REPORTED_DESIRED 
            return answer_topic, answer_payload

        answer_topic = ""
        answer_payload = ""

    elif action == "get": # these come from things
        payload = "" # we ignore payload, as this is just a request to receive delta
        delta = db.get_delta(thing)
        add_time(delta)
        answer_topic = "things/%s/delta" % thing
        answer_payload = to_compact_json(delta)
    else:
        log.error("We got a message on a topic we should not be listening to: %s - %s" % (topic, payload))
        answer_topic = ERROR_TOPIC
        answer_payload = MESSAGE_NOT_HANDLED

    return answer_topic, answer_payload


class MqttOperator:
    def __init__(self, working_directory = DIR): 
        self.db = db_driver.DatabaseDriver(working_directory)
        self.client = mqtt.Client()
        username, password = parse_username_password()
        self.client.username_pw_set(username, password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def operate(self):
        self.client.connect("localhost")
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        log = logger.of("on_connect")
        log.info("Connected with result code %d" % rc)
        client.subscribe("things/+/update")
        client.subscribe("things/+/get")


    def on_message(self, client, userdata, msg):
        log = logger.of("on_message")
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        log.info("[%s] %s" % (topic, payload))
        answer_topic, answer_payload = get_answer(self.db, topic, payload)
        if answer_topic:
            log.info("Answering [%s] %s" % (answer_topic, answer_payload))
            self.client.publish(answer_topic, answer_payload)
        
if __name__ == '__main__':
    mqtt_operator = MqttOperator()
    mqtt_operator.operate()
