#!/www/zelenik/venv/bin/python

from logger import Logger

from datetime import datetime, timedelta, timezone

import db_driver
from db_driver import pretty_json

from state_processor import parse_isoformat

import threading 

from pathlib import Path

from dateutil import tz
local_timezone = tz.gettz('Europe/Sofia')

logger = Logger("uptime_monitor")

DIR = '/www/zelenik/'

RUN_EVERY = 30 # seconds

def local_day_hour_minute(dt):
    log = logger.of('local_day_hour_minute')
    utc_dt = dt.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(local_timezone)
    return local_dt.strftime("%Y-%m-%d %H:%M")

class UptimeMonitor:
    def __init__(self, working_directory = DIR):
        self.working_directory = working_directory
        self.db = db_driver.DatabaseDriver(working_directory)

        self.db_path = Path(self.working_directory) / 'db'

    def monitor(self):
        log = logger.of('monitor')

        if not self.running:
            return

        if not self.db_path.is_dir():
            log.error('Database path %s is not a directory.' % self.db_path)
            self.stop()
            return

        things = self.db.get_thing_list()

        summary = {'up': [], 'down': [], 'error': []}

        for thing in things:
            key, alias = self.check_uptime(thing)
            thing_alias = {'thing': thing, 'alias': alias}
            summary[key].append(thing_alias)
        
        thing_summary = self.db_path / 'thing-summary.json'

        with thing_summary.open('w') as f:
            f.write(pretty_json(summary))

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
            return 'error', aliased_thing

        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        timestamp = parse_isoformat(timestamp_string)
        if timestamp < five_minutes_ago:
            log.error('%s is down. Last seen: %s' % (aliased_thing, local_day_hour_minute(timestamp)))
            return 'down', aliased_thing
        else:
            boot_utc_string = enchanted['state'].get('boot_utc')
            if boot_utc_string is None:
                log.error('Enchanted for %s does not contain boot_utc: %s' % (aliased_thing, enchanted))
                return 'error', aliased_thing
            up_since = parse_isoformat(boot_utc_string)
            log.warning('%s is up since: %s' % (aliased_thing, local_day_hour_minute(up_since)))
            return 'up', aliased_thing

    def start(self):
        logger.of('start').info('Starting')
        self.running = True
        t = threading.Timer(RUN_EVERY, self.monitor)
        t.start()

    def stop(self):
        logger.of('stop').info('Stopping')
        self.running = False

if __name__ == '__main__':
    monitor = UptimeMonitor()
    monitor.start()

