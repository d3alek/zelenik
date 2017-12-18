#!/www/zelenik/venv/bin/python

from logger import Logger
import subprocess
import threading 
import requests
import json
import time
from db_driver import timestamp

from socket import gethostname

logger = Logger("server_operator")

DIR = '/www/zelenik/db'
AUTHENTICATION_KEY = '/www/zelenik/secret/otselo_id_rsa'

RUN_EVERY = 3*60 # seconds

from datetime import timezone, datetime
from dateutil import tz

import psutil, os

local_timezone = tz.gettz('Europe/Sofia')
def local_day_hour_minute(dt):
    if dt == None:
        return "none"
    utc_dt = dt.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(local_timezone)
    return local_dt.strftime("%Y-%m-%d %H:%M")

def retry_on_none(func, times):
    for attempt in range(times):
        result = func()
        if result:
            return result
        time.sleep(1)

    return None

def get_master_hostname():
    log = logger.of('get_master_hostname')
    try:
        r = requests.get('http://otselo.eu/hostname.html', timeout=1)
        r.raise_for_status()
        master = r.text.strip()
        log.info('Master hostname is %s' % master)
        return master
    except requests.HTTPError:
        log.error('Unsuccessful http request to master')
    except requests.Timeout:
        log.error('Timeout when connecting to master')
    except requests.ConnectionError:
        log.error('Network problems when connecting to master', traceback=True)
    return None

# source: https://stackoverflow.com/a/4559733
def get_process_start_time():
    p = psutil.Process(os.getpid())
    return datetime.utcfromtimestamp(p.create_time())

class ServerOperator:
    def __init__(self, source_directory = DIR, destination_directory = DIR):
        self.source_directory = source_directory
        self.destination_directory = destination_directory

    def get_state(self):
        return {'hostname': self.hostname, 'role': self.role, 'type': 'server', 'boot_utc': timestamp(get_process_start_time())}

    def check_in(self):
        log = logger.of('check_in')
        try:
            r = requests.post('http://otselo.eu/db/%s/update' % self.hostname, data={'reported': json.dumps(self.get_state())}, timeout=3, allow_redirects=False)
            r.raise_for_status()
            log.info('Successfully checked in')
            return 'Success'
        except requests.HTTPError:
            log.error('Unsuccessful http request to server')
        except requests.Timeout:
            log.error('Timeout when connecting to server')
        except requests.ConnectionError:
            log.error('Network problems when connecting to server', traceback=True)

        return None

    def operate(self):
        log = logger.of('operate')
        if not self.running:
            return

        self.hostname = gethostname()
        self.master_hostname = retry_on_none(get_master_hostname, 3)

        if self.master_hostname:
            self.role = 'master' if self.master_hostname == self.hostname else 'slave'
            if self.role == 'master':
                log.info('Master mode, skipping sync up')
            else:
                self.slave_operate()
               
            retry_on_none(self.check_in, 3)

        else:
            log.error("server is down")

        if self.running:
            t = threading.Timer(RUN_EVERY, self.operate)
            t.start()

    def slave_operate(self, destination_host="otselo@otselo.eu"):
        log = logger.of('slave_operate')
        log.info('Slave mode, sync-up two-way')

        self.sync_to(destination_host, new_files=False)
        self.sync_from(destination_host)

    def start(self):
        logger.of('start').info('Starting')
        self.running = True
        self.operate()

    def stop(self):
        logger.of('stop').info('Stopping')
        self.running = False

    def sync_to(self, host, authenticate=True, new_files=True):
        source_descriptor = "%s/" % self.source_directory
        if host == 'localhost':
            destination_descriptor = self.destination_directory
        else:
            destination_descriptor = "%s:%s" % (host, self.destination_directory)
        sync( source_descriptor, destination_descriptor, authenticate, new_files)

    def sync_from(self, host, authenticate=True):
        if host == 'localhost':
            source_descriptor = "%s/" % self.destination_directory
        else:
            source_descriptor = "%s:%s/" % (host, self.destination_directory)
        destination_descriptor = self.source_directory
        sync(source_descriptor, destination_descriptor, authenticate)

# copies source contents into destination
def sync(source, destination, authenticate=True, new_files=True):
    log = logger.of('sync')
    authentication = '--rsh=ssh -p8902 -o "StrictHostKeyChecking no" -i ' + AUTHENTICATION_KEY
    existing = "--existing"

    command = ["rsync", "-azu", source, destination]
    if authenticate:
        command.insert(2, authentication)
    if not new_files:
        command.insert(3, existing)

    log.info(" ".join(command))
    try:
        subprocess.check_call(command)
        log.info('Backup successful')
    except subprocess.CalledProcessError as e:
        if e.returncode == 24:
            pass # this happens when some files were indexed but were deleted before rsync finished - this tends to happen with our database
        else:
            log.error('failed to sync %s -> %s' % (source, destination), traceback=True)

if __name__ == '__main__':
    server_operator = ServerOperator()
    server_operator.start()
