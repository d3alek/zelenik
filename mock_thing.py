#!/www/zelenik/venv/bin/python

import paho.mqtt.client as mqtt
import db_driver
import json
import time
import threading
from mqtt_operator import parse_username_password
from state_processor import parse_action

from datetime import datetime as dt
from datetime import timedelta

import random

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
last_publish = None
first_awake = True

def info(method, message):
    print("  mock_thing/%s: %s" % (method, message))

def load_actions(actions):
    global config_changed
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
    global config_changed
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
    global config_changed
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    config_changed = False
    info("on_message", "%s" % payload)

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

def update_senses():
    state['senses'] = {'mock-sense': random.randint(0, 100)}

write_to_int = {'low': 0, 'high': 1}
def do_actions():
    global config_changed
    previous_mode = state['mode']
    mode = {}
    for sense, value in state['senses'].items():
        for action_key, action_value in state['config']['actions'].items():
            target_sense, action = parse_action(action_key, action_value)
            if target_sense == sense:
                write_int = write_to_int[action['write']]
                mode_key = str(action['gpio'])
                threshold = action['threshold']
                delta = action['delta']

                if value <= threshold - delta:
                    config_changed = True
                    mode[mode_key] = (write_int + 1) % 2
                elif value >= threshold + delta:
                    config_changed = True
                    mode[mode_key] = write_int
                else:
                    mode[mode_key] = previous_mode[key]
    info('do_actions', mode)
    state['mode'] = mode
             
def publish_state():
    global state
    reported = {"state": {"reported": state}}
    client.publish("things/%s/update" % NAME, json.dumps(reported))
    info('publish_state', 'published state')

def wake_up():
    global last_publish, config_changed, state, first_awake
    info('wake_up', 'woke up')
    config_changed = False
    if first_awake:
        publish_state()
        first_awake = False

    client.publish("things/%s/get" % NAME, "{}")
    info('wake_up', 'waiting for delta from server')
    time.sleep(2)
    update_senses()
    do_actions()
    if config_changed or not last_publish or last_publish + timedelta(minutes=1) < dt.now():
        last_publish = dt.now()
        publish_state(); 
    else:
        info('wake_up', 'too soon to publish')

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
