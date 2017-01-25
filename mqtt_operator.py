import paho.mqtt.client as mqtt
import db_driver
import json
import re

OPERATOR_ERROR_TOPIC = "operator_error"
MESSAGE_NOT_HANDLED = '{"reason": "Message not handled. See mqtt_operator logs for details"}'
MESSAGE_NOT_JSON = '{"reason": "Message not a valid json. See mqtt_operator logs for details"}'
WRONG_FORMAT_STATE = '{"reason": "Message payload did not begin with state object. See mqtt_operator logs for details"}'
WRONG_FORMAT_REPORTED_DESIRED = '{"reason": "Message payload did not begin with state/reported or state/desired objects. See mqtt_operator logs for details"}'

def parse_thing_action(topic):
    match = re.match(r'things\/([a-zA-Z0-9-]+)\/(\w+)', topic)
    if not match:
        print("! parse_thing_action: Could not parse thing and action from topic %s" % topic)
        return "", ""
    thing = match.group(1)
    action = match.group(2)
    return thing, action


class MqttOperator:
    def __init__(self, db_location = '/home/pi/zelenik/db'):
        self.db = db_driver.DatabaseDriver(db_location)
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def operate(self):
        self.client.connect("localhost")
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code", str(rc))
        client.subscribe("/things/+/update")
        client.subscribe("/things/+/get")

    def get_answer(self, topic, payload_string):

        db = self.db

        try:
            payload = json.loads(payload_string)
        except ValueError:
            print("! get_answer: Payload is not a valid json. %s - %s" % (topic, payload_string))
            answer_topic = OPERATOR_ERROR_TOPIC
            answer_payload = MESSAGE_NOT_JSON
            return answer_topic, answer_payload

        thing, action = parse_thing_action(topic)

        if action == "update":
            if not payload.get("state"):
                print("! get_answer: Update payload does not begin with a state object. %s - %s" % (topic, payload))
                answer_topic = OPERATOR_ERROR_TOPIC
                answer_payload = WRONG_FORMAT_STATE
                return answer_topic, answer_payload

            if payload["state"].get("reported"): # these come from things
                #TODO handle the case where update explodes with exception
                db.update(thing, "reported", payload["state"]["reported"])
            elif payload["state"].get("desired"): # these come from controllers (UI, console)
                #TODO handle the case where update explodes with exception
                db.update(thing, "desired", payload["state"]["desired"])
            else:
                print("! get_answer: Update contains neither reported nor desired. %s - %s" % (topic, payload))
                answer_topic = OPERATOR_ERROR_TOPIC
                answer_payload = WRONG_FORMAT_REPORTED_DESIRED 
                return answer_topic, answer_payload

            answer_topic = ""
            answer_payload = ""
        elif action == "get": # these come from things
            payload = "" # we ignore payload, as this is just a request to receive delta
            delta = db.get_delta(thing, "reported", "desired")
            answer_topic = "things/%s/delta" % thing
            answer_payload = str(delta)
        else:
            print("! get_answer: We got a message on a topic we should not be listening to: %s - %s" % (topic, payload))
            answer_topic = OPERATOR_ERROR_TOPIC
            answer_payload = MESSAGE_NOT_HANDLED

        return answer_topic, answer_payload

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = str(msg.payload)
        print(topic, payload)
        answer_topic, answer_payload = self.get_answer(topic, payload)
        if answer_topic:
            mqtt.publish(answer_topic, answer_payload)
        

if __name__ == '__main__':
    mqtt_operator = MqttOperator()
    mqtt_operator.operate()
