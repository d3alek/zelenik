#!/www/zelenik/venv/bin/python
import sys
from socket import gethostname

import smtplib
from email.mime.text import MIMEText

from logger import Logger
logger = Logger("error_reporter")

from systemd import journal

import time

from uptime_monitor import UptimeMonitor, down_message, up_message

DIR = '/www/zelenik/'
HUMAN_OPERATOR = "akodzhabashev@gmail.com"
ALWAYS_REPORT_FROM = ['uptime_monitor']

class ErrorReporter:
    def __init__(self):
        self.hostname = gethostname()

    def report(self):
        log = logger.of('report')
        j = journal.Reader()
        j.log_level(journal.LOG_WARNING)
        j.this_boot()
        j.this_machine()
        j.seek_tail()
        j.get_previous()

        already_reported = set()

        while True:
            result = j.wait()
            if result == journal.APPEND:
                for entry in j:
                    message = entry.get('MESSAGE')
                    logger_name = entry.get('LOGGER')
                    unit = entry.get('_SYSTEMD_UNIT')
                    priority = entry.get('PRIORITY')

                    if priority in [journal.LOG_ERR, journal.LOG_WARNING] and message not in already_reported:
                        subject = message.split('\n')[0].strip()
                        notify_human_operator(subject, self.sign(message, logger_name)) 
                        if logger_name not in ALWAYS_REPORT_FROM:
                            already_reported.add(message)

    def sign(self, message, source):
        return message + "\n\n%s@%s" % (source, self.hostname)

def notify_human_operator(subject, body):
    msg = MIMEText(body, _subtype='plain', _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = "reporter@otselo.eu"
    msg['To'] = HUMAN_OPERATOR
    log = logger.of('notify_human_operator')

    try:
        with smtplib.SMTP('localhost') as s:
            s.send_message(msg)
        log.info('Sent error report to %s' % HUMAN_OPERATOR)
    except ConnectionRefusedError:
        log.info('Could not send email:\n%s\nDecoded message:\n%s' % (msg, body))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        logger.of('__main__').info("Sending direct email to human operator and quitting")
        notify_human_operator("Testing...", sys.argv[1])

    else:
        reporter = ErrorReporter()
        reporter.report()
