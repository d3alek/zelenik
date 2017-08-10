#!/www/zelenik/venv/bin/python

from logger import Logger
import subprocess
import threading 
import db_driver
import requests

from socket import gethostname

logger = Logger("server_operator")

DIR = '/www/zelenik/'

RUN_EVERY = 5*60 # seconds
UP_SINCE = '%s is up since: %s'
DOWN_LAST_SEEN = '%s is down. Last seen: %s'

def local_day_hour_minute(dt):
    if dt == None:
        return "none"
    utc_dt = dt.replace(tzinfo=timezone.utc)
    local_dt = utc_dt.astimezone(local_timezone)
    return local_dt.strftime("%Y-%m-%d %H:%M")


def get_server_hostname():
    log = logger.of('get_server_hostname')
    try:
        r = requests.get('http://otselo.eu/hostname.html', timeout=1)
        if r.status_code == 200:
            master = r.text.strip()
            log.info('Master hostname is %s' % master)
            return master
        else:
            log.warning('Connected to server but could not get hostname')
            return None
    except:
        log.error('Could not connect to server', traceback=True)
        return None

class ServerOperator:
    def __init__(self, working_directory = DIR):

        self.working_directory = working_directory
        self.db = db_driver.DatabaseDriver(working_directory)

    def operate(self):
        log = logger.of('operate')
        if not self.running:
            return

        server_hostname = get_server_hostname()

        if server_hostname:
            if server_hostname == gethostname():
                log.info('Master mode, skipping backup')
            else:
                log.info('Slave mode, backing up')
                log.warning(UP_SINCE % (server_hostname, local_day_hour_minute(self.db.get_timestamp())))
                log.info(" ".join(["rsync", "-az", "--delete", "--rsh=ssh -p8902 -i " + DIR + "secret/otselo_id_rsa", "otselo@otselo.eu:/www/zelenik/db", DIR]))
                try:
                    subprocess.check_call(["rsync", "-az", "--delete", "--rsh=ssh -p8902 -i " + DIR + "secret/otselo_id_rsa", "otselo@otselo.eu:/www/zelenik/db", DIR])
                    log.info('Backup successful')
                except:
                    log.error('Failed to backup', traceback=True)
        else:
            log.error(DOWN_LAST_SEEN % ("otselo.eu", local_day_hour_minute(self.db.get_timestamp())))
            # TODO maybe retry, if failing for a while assume domain

        if self.running:
            t = threading.Timer(RUN_EVERY, self.operate)
            t.start()

    def start(self):
        logger.of('start').info('Starting')
        self.running = True
        #t = threading.Timer(RUN_EVERY, self.operate)
        #t.start()
        self.operate()

    def stop(self):
        logger.of('stop').info('Stopping')
        self.running = False

if __name__ == '__main__':
    server_operator = ServerOperator()
    server_operator.start()
