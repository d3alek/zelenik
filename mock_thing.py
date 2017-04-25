#!/www/zelenik/venv/bin/python

import paho.mqtt.client as mqtt
import db_driver
import json
import time
import threading
from mqtt_operator import parse_username_password
from state_processor import parse_action, timestamp_to_seconds

from datetime import datetime as dt
from datetime import timedelta

import random

import argparse

MAX_ACTIONS_SIZE = 5
NAME = "mock-thing"
DEFAULT_STATE = {
        "config": {
            "actions": {},
            "gpio": {
                "4": "OneWire"
            },
            "sleep": 0,
            "mode": {}
        },
        "write": {},
        "lawake": 0,
        "b": -1, # seconds from boot
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
first_awake = True
start_seconds = 0

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
            if sense == ex_sense and action['gpio'] == ex_action['gpio']:
                found_same_sense_gpio = True
                if action['delta'] == -2:
                    info('load_actions', 'Removing %s because delta is -2' % ex_action)
                else:
                    info('load_actions', 'Replacing %s' % ex_action)
                    new_actions[key] = value
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
        make_device_pin_pairing(gpio_config, pin_number, str(value))
        config_changed = True

    return gpio_config

def load_mode(mode):
    global config_changed
    mode_config = state['config'].get('mode', {})
    for pin, value in mode.items():
        mode_config[pin] = value
        config_changed = True

    return mode_config

def on_connect(client, userdata, flags, rc):
    info("on_connect", "Connected with result code %d" % rc)
    client.subscribe("things/%s/delta" % NAME)

    threading.Timer(2, wake_up).start()

def seconds(): # seconds from boot
    return int(time.time()) - start_seconds

def on_message(client, userdata, msg):
    global config_changed
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    config_changed = False
    info("on_message", "%s" % payload)

    config = state['config']
    delta = json.loads(payload)
    if delta.get('version') is not None:
        #TODO
        pass
    if delta.get('sleep') is not None:
        config_changed = True
        config['sleep'] = int(delta['sleep'])
    if delta.get('gpio') is not None:
        load_gpio_config(delta['gpio'])
    if delta.get('mode') is not None:
        load_mode(delta['mode'])
    if delta.get('actions') is not None:
        load_actions(delta['actions'])
    if delta.get('t') is not None:
        boot_time = delta.get('t') - seconds()
        state['b'] = boot_time

def seconds_today():
    boot_seconds = state['b']
    return (boot_seconds + seconds()) % (60*60*24)

def update_senses():
    state['senses'] = {'mock-sense': random.randint(0, 100), "time": seconds_today()}

write_to_int = {'low': 0, 'high': 1}
def do_actions():
    global config_changed
    config = state['config']
    mode = config['mode']
    previous_write = state['write']
    write = {}
    actions = config['actions']
    auto_actions = []
    for action_key, action_value in actions.items():
        target_sense, action = parse_action(action_key, action_value)
        gpio_string = str(action['gpio'])
        m = mode.get(gpio_string, 'a')
        if m == 'a':
            auto_actions.append((target_sense, action)) 
        else:
            info('do_actions', 'Not doing action %s:%s due to gpio mode %s' % (target_sense, action, m))

    for sense, value in state['senses'].items():
        for target_sense, action in auto_actions:
            write_key = str(action['gpio'])
    
            if target_sense == sense:
                write_int = write_to_int[action['write']]
                threshold = action['threshold']
                delta = action['delta']
                if sense == "time":
                    threshold = timestamp_to_seconds(threshold)
                    delta = timestamp_to_seconds(delta)
                    
                    if value >= threshold and value <= threshold + delta:
                        write[write_key] = write_int
                    else:
                        write[write_key] = (write_int + 1) % 2

                else:
                    if value <= threshold - delta:
                        write[write_key] = (write_int + 1) % 2
                    elif value >= threshold + delta:
                        write[write_key] = write_int
                    else:
                        write[write_key] = previous_write[key]

    for key, value in mode.items():
        if value != 'a':
            write[key] = value

    info('do_actions', write)
    state['write'] = write 

def publish_state():
    global state
    reported = {"state": {"reported": state}}
    client.publish("things/%s/update" % NAME, json.dumps(reported))
    info('publish_state', 'published state')

def wake_up():
    global config_changed, state, first_awake, start_seconds
    info('wake_up', 'woke up')
    config_changed = False
    if first_awake:
        start_seconds = int(time.time())
        first_awake = False

    client.publish("things/%s/get" % NAME, "{}")
    info('wake_up', 'waiting for delta from server')
    time.sleep(2)
    update_senses()
    do_actions()
    publish_state(); 

    threading.Timer(10, wake_up).start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulate a Zelenik device')
    parser.add_argument('--server', action='store', default="localhost", help='Server to connect to (defaults to localhost)')
    parser.add_argument('--port', type=int, action='store', default=1883, help='Port to use to connect (defaults to 1883)')
    args = parser.parse_args()

    db = db_driver.DatabaseDriver(DIR)
    client = mqtt.Client()

    username, password = parse_username_password()
    client.username_pw_set(username, password)

    client.on_connect = on_connect
    client.on_message = on_message

    print("Connecting to %s:%s" % (args.server, args.port))
    client.connect(args.server, args.port)
    client.loop_forever()
