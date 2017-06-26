#!/www/zelenik/venv/bin/python

from logger import Logger

from datetime import datetime, timedelta, timezone

import db_driver

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

        for thing_path in self.db_path.iterdir():
            thing = thing_path.name
            if thing in ('na', 'stado', '.gitignore'):
                continue
            self.check_uptime(thing)

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
            return

        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        timestamp = parse_isoformat(timestamp_string)
        if timestamp < five_minutes_ago:
            log.error('%s is down. Last seen: %s' % (aliased_thing, local_day_hour_minute(timestamp)))
        else:
            up_since = parse_isoformat(enchanted['state']['boot_utc'])
            log.warning('%s is up since: %s' % (aliased_thing, local_day_hour_minute(up_since)))

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


