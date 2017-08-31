#!/www/zelenik/venv/bin/python

from logger import Logger
import subprocess
import threading 
import db_driver
import requests
import json
import time

from socket import gethostname

logger = Logger("server_operator")

DIR = '/www/zelenik/'

RUN_EVERY = 5*60 # seconds

from datetime import timezone
from dateutil import tz
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
    log = logger.of('get_server_hostname')
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



class ServerOperator:
    def __init__(self, working_directory = DIR):

        self.working_directory = working_directory
        self.db = db_driver.DatabaseDriver(working_directory)

    def get_state(self):
        db_last_modified = self.db.last_modified()
        return {'db_last_modified': db_driver.timestamp(db_last_modified)}

    def check_in(self):
        log = logger.of('check_in')
        hostname = gethostname()
        try:
            r = requests.post('http://otselo.eu/db/%s/update' % hostname, data={'reported': json.dumps(self.get_state())}, timeout=3, allow_redirects=False)
            r.raise_for_status()
            master = r.text.strip()
            log.info('Master hostname is %s' % master)
            return master
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

        hostname = gethostname()
        master_hostname = retry_on_none(get_master_hostname, 3)

        if master_hostname:
            if master_hostname == hostname:
                log.info('Master mode, skipping backup')
            else:
                log.info('Slave mode, backing up')
                log.info(" ".join(["rsync", "-az", "--delete", "--rsh=ssh -p8902 -i " + DIR + "secret/otselo_id_rsa", "otselo@otselo.eu:/www/zelenik/db", DIR]))
                try:
                    subprocess.check_call(["rsync", "-az", "--delete", "--rsh=ssh -p8902 -i " + DIR + "secret/otselo_id_rsa", "otselo@otselo.eu:/www/zelenik/db", DIR])
                    log.info('Backup successful')
                except CalledProcessError as e:
                    if e.returncode == 24:
                        pass # this happens when some files were indexed but were deleted before rsync finished - this tends to happen with our database
                    else:
                        log.error('%s failed to backup server' % hostname, traceback=True)

            retry_on_none(self.check_in, 3)

        else:
            log.error("server is down\nLast backup: %s" % local_day_hour_minute(self.db.last_modified()))

        if self.running:
            t = threading.Timer(RUN_EVERY, self.operate)
            t.start()

    def start(self):
        logger.of('start').info('Starting')
        self.running = True
        self.operate()

    def stop(self):
        logger.of('stop').info('Stopping')
        self.running = False

if __name__ == '__main__':
    server_operator = ServerOperator()
    server_operator.start()
