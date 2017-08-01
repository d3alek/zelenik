#!/www/zelenik/venv/bin/python

from logger import Logger

from datetime import datetime, timedelta, timezone

import db_driver
from db_driver import pretty_json

from state_processor import parse_isoformat

import threading 

from pathlib import Path

import json

from dateutil import tz
local_timezone = tz.gettz('Europe/Sofia')

from socket import gethostname
import requests

logger = Logger("uptime_monitor")

DIR = '/www/zelenik/'

RUN_EVERY = 30 # seconds
THING_SUMMARY = 'thing-summary.json'
UP_SINCE = '%s is up since: %s'
DOWN_LAST_SEEN = '%s is down. Last seen: %s'

def local_day_hour_minute(dt):
    if dt == None:
        return "none"
    utc_dt = dt.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(local_timezone)
    return local_dt.strftime("%Y-%m-%d %H:%M")

class UptimeMonitor:
    def __init__(self, working_directory = DIR):
        self.working_directory = working_directory
        self.db = db_driver.DatabaseDriver(working_directory)

        self.db_path = Path(self.working_directory) / 'db'
        self.hostname = gethostname()

    def monitor(self):
        log = logger.of('monitor')

        if not self.running:
            return

        if not self.db_path.is_dir():
            log.error('Database path %s is not a directory.' % self.db_path)
            self.stop()
            return

        slave = True
        r = requests.get('http://otselo.eu/hostname.html')
        if r.status_code == 200:
            master = r.text.strip()
        else:
            master = "otselo.eu"
            log.error(DOWN_LAST_SEEN % (master, local_day_hour_minute(self.db.get_timestamp())))

        if master == self.hostname:
            log.info('Master host - monitoring things uptime')

            things = self.db.get_thing_list()

            summary = {'up': [], 'down': [], 'error': []}

            for thing in things:
                key, alias, since = self.check_uptime(thing)
                value = {'thing': thing, 'alias': alias, 'since': since }
                summary[key].append(value)
            
            thing_summary = self.db_path / THING_SUMMARY

            with thing_summary.open('w') as f:
                f.write(pretty_json(summary))
        else:
            log.info('Slave host - only monitoring master uptime')
        if self.running:
            t = threading.Timer(RUN_EVERY, self.monitor)
            t.start()

    def check_uptime(self, thing):
        log = logger.of('check_uptime') 
        enchanted = self.db.load_state(thing, 'enchanted')
        timestamp_string = enchanted.get('timestamp_utc')
        aliased_thing = self.db.alias_thing(thing)
        if timestamp_string is None:
            log.error('Enchanted for %s does not contain timestamp: %s' % (aliased_thing, enchanted))
            return 'error', aliased_thing, None

        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        timestamp = parse_isoformat(timestamp_string)
        if timestamp < five_minutes_ago:
            since = local_day_hour_minute(timestamp)
            log.error(DOWN_LAST_SEEN % (aliased_thing, since))
            return 'down', aliased_thing, since
        else:
            boot_utc_string = enchanted['state'].get('boot_utc')
            if boot_utc_string is None:
                log.error('Enchanted for %s does not contain boot_utc: %s' % (aliased_thing, enchanted))
                since = local_day_hour_minute(timestamp)
                return 'error', aliased_thing, None
            up_since = parse_isoformat(boot_utc_string)
            since = local_day_hour_minute(up_since)
            log.warning(UP_SINCE  % (aliased_thing, since))
            return 'up', aliased_thing, since

    def start(self):
        logger.of('start').info('Starting')
        self.running = True
        t = threading.Timer(RUN_EVERY, self.monitor)
        t.start()

    def stop(self):
        logger.of('stop').info('Stopping')
        self.running = False

    def messages_from_thing_summary(self):
        thing_summary = self.db_path / THING_SUMMARY

        with thing_summary.open() as f:
            summary = json.loads(f.read())

        messages = []
        for value in summary['up']:
            thing = value['thing']
            alias = value['alias']
            since = value['since']

            messages.append(UP_SINCE % (alias, since))

        for value in summary['down']:
            thing = value['thing']
            alias = value['alias']
            since = value['since']

            messages.append(DOWN_LAST_SEEN % (alias, since))
        
        return messages

if __name__ == '__main__':
    monitor = UptimeMonitor()
    monitor.start()


