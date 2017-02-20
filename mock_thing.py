#!/www/zelenik/venv/bin/python

import paho.mqtt.client as mqtt
import db_driver
import json
import time
import threading
from mqtt_operator import parse_username_password
from state_processor import parse_action

MAX_ACTIONS_SIZE = 5
NAME = "mock-thing"
DEFAULT_STATE = {
        "config": {
            "actions": {},
            "gpio": {
                "4": "OneWire"
            },
            "sleep": 0
        },
        "lawake": 0,
        "mode": {},
        "senses": {
            "mock-sense": 0
        },
        "state": "local_publish",
        "version": "mock",
        "voltage": 3123,
        "wifi": "d3home"
    }

state = DEFAULT_STATE

DIR = '/www/zelenik/'
config_changed = False

def info(method, message):
    print("  mock_thing/%s: %s" % (method, message))

def load_actions(actions):
    for key, value in actions.items():
        config_changed = True 
        sense, action = parse_action(key, value)
        found_same_sense_gpio = False

        existing_actions = state['config']['actions']
        new_actions = {}
        for ex_key, ex_value in existing_actions.items():
            ex_sense, ex_action = parse_action(ex_key, ex_value)
            if sense == ex_sense and action['gpio'] == ex['gpio']:
                found_same_sense_gpio = True
                if action['delta'] == -2:
                    info('load_actions', 'Removing %s because delta is -2' % old_action)
                else:
                    info('load_actions', 'Replacing %s' % old_action)
                    new_actions[key] = "%s~%s" % (action['threshold'], action['delta'])
            else:
                new_actions[ex_key] = ex_value

        if not found_same_sense_gpio:
            if action['delta'] == -2:
                info('load_actions', 'Not adding action %s because delta is -2' % action)
            elif len(existing_actions.items()) + 1 >= MAX_ACTIONS_SIZE:
                info('load_actions', 'Too many actions already, ignoring this one %s' % action)
            else:
                new_actions[key] = value


        state['config']['actions'] = new_actions

def make_device_pin_pairing(gpio_config, pin_number, device):
    if device in ['DHT11', 'DHT22', 'OneWire']:
        gpio_config[str(pin_number)] = device

def load_gpio_config(gpio):
    gpio_config = state['config'].get('gpio', {})
    for key, value in gpio.items():
        pin_number = int(key)
        if pin_number == 0:
            continue
        config_changed = True
        make_device_pin_pairing(gpio_config, pin_number, str(value))
    return gpio_config

def on_connect(client, userdata, flags, rc):
    info("on_connect", "Connected with result code %d" % rc)
    client.subscribe("things/%s/delta" % NAME)

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    config_changed = False

    config = state['config']
    new_config = json.loads(payload)
    if new_config.get('version') is not None:
        #TODO
        pass
    if new_config.get('sleep') is not None:
        config_changed = True
        config['sleep'] = int(new_config['sleep'])
    if new_config.get('gpio') is not None:
        load_gpio_config(new_config['gpio'])
    if new_config.get('actions') is not None:
        load_actions(new_config['actions'])

def wake_up():
    info('wake_up', 'Woke up')
    client.publish("things/%s/get" % NAME, "{}")
    time.sleep(2)
    reported = {"state": {"reported": state}}
    client.publish("things/%s/update" % NAME, json.dumps(reported))
    threading.Timer(10, wake_up).start()

if __name__ == '__main__':
    db = db_driver.DatabaseDriver(DIR)
    client = mqtt.Client()

    username, password = parse_username_password()
    client.username_pw_set(username, password)

    client.on_connect = on_connect
    client.on_message = on_message

    threading.Timer(2, wake_up).start()
    client.connect("localhost")
    client.loop_forever()


