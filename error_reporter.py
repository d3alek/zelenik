#!/www/zelenik/venv/bin/python
import sys

import smtplib
from email.mime.text import MIMEText

from logger import Logger
logger = Logger("error_reporter")

import select
from systemd import journal

DIR = '/www/zelenik/'
HUMAN_OPERATOR = "akodzhabashev@gmail.com"

class ErrorReporter:
    def report(self):
        log = logger.of('report')
        j = journal.Reader()
        j.log_level(journal.LOG_WARNING)
        j.this_boot()
        j.this_machine()
        j.seek_tail()
        j.get_previous()
        p = select.poll()

        p.register(j, j.get_events())

        reported = set()

        while True:
            p.poll()
            for entry in j:
                error_message = entry['MESSAGE']
                logger_name = entry['LOGGER']
                unit = entry['_SYSTEMD_UNIT']
                print('Message: %s' % error_message)
                print('Logger: %s' % logger_name)
                print('Unit: %s' % unit)
                if entry['PRIORITY'] == journal.LOG_ERR:
                    if error_message in reported:
                        log.info('Already reported this error')
                    else:
                        notify_human_operator('Error from %s' % logger_name, error_message)
                        reported.add(error_message)

def notify_human_operator(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = "reporter@otselo.eu"
    msg['To'] = HUMAN_OPERATOR

    with smtplib.SMTP('localhost') as s:
        s.send_message(msg)

    logger.of('notify_human_operator').info('Sent error report to %s' % HUMAN_OPERATOR)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        logger.of('__main__').info("Sending direct email to human operator and quitting")
        notify_human_operator("Testing...", sys.argv[1])

    else:
        reporter = ErrorReporter()
        reporter.report()
