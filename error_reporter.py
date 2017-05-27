#!/www/zelenik/venv/bin/python

import paho.mqtt.client as mqtt
import sys

import smtplib
from email.message import EmailMessage
from email.headerregistry import Address

ERROR_TOPIC = "error"
DIR = '/www/zelenik/'
HUMAN_OPERATOR = "akodzhabashev@gmail.com"

def info(method, message):
    print("  error_reporter/%s: %s" % (method, message))

def error(method, message):
    print("! error_reporter/%s: %s" % (method, message))

def parse_username_password():
    with open(DIR + 'secret/mqtt_password_file') as f:
        contents = f.read()
    username, _ = contents.split(':')

    with open(DIR + 'secret/mqtt_password') as f:
        password = f.read()

    return username.strip(), password.strip()

class ErrorReporter:
    def __init__(self): 
        self.client = mqtt.Client()
        username, password = parse_username_password()
        self.client.username_pw_set(username, password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def operate(self):
        self.client.connect("localhost")
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        info("on_connect", "Connected with result code %d" % rc)
        client.subscribe(ERROR_TOPIC)

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_string = msg.payload.decode('utf-8')
        info("on_message", "[%s] %s | user: %s" % (topic, payload_string, userdata))
        notify_human_operator(payload_string)


def notify_human_operator(body):
    msg = EmailMessage()
    msg['Subject'] = 'Zelenik Error Report'
    msg['From'] = Address("Zelenik Error Reporter", 'reporter", "otselo.eu')
    msg['To'] = Address("", "akodzhabashev", "gmail.com")
    msg.set_content(body)

    with smtplib.SMTP('localhost') as s:
        s.send_message(msg)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        info("main", "Sending direct email to human operator and quitting")
        notify_human_operator(sys.argv[1])

    else:
        mqtt_operator = ErrorReporter()
        mqtt_operator.operate()
