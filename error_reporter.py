#!/www/zelenik/venv/bin/python
import sys

import smtplib
from email.mime.text import MIMEText

from logger import Logger
logger = Logger("error_reporter")

import select
from systemd import journal

import time

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
            p.poll(250)
            for entry in j:
                message = entry['MESSAGE']
                logger_name = entry['LOGGER']
                unit = entry['_SYSTEMD_UNIT']
                if entry['PRIORITY'] == journal.LOG_WARNING and "is up" in message and message not in reported:
                    thing = message.split("is up")[0].strip()
                    notify_human_operator('%s is up' % thing, message) 
                    reported.add(message)

                if entry['PRIORITY'] == journal.LOG_ERR:
                    if message in reported:
                        log.info('Already reported this error')
                    else:
                        if "is down" in message:
                            thing = message.split("is down")[0].strip()
                            subject = '%s is down' % thing
                        else:
                            subject = 'Error from %s' % logger_name

                        notify_human_operator(subject, message + "\n%s" % unit) 
                        reported.add(message)
            time.sleep(1)
            log.info('Polling for new log entries...')


def notify_human_operator(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = "reporter@otselo.eu"
    msg['To'] = HUMAN_OPERATOR
    log = logger.of('notify_human_operator')

    try:
        with smtplib.SMTP('localhost') as s:
            s.send_message(msg)
        log.info('Sent error report to %s' % HUMAN_OPERATOR)
    except ConnectionRefusedError:
        log.info('Could not send email %s' % msg)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        logger.of('__main__').info("Sending direct email to human operator and quitting")
        notify_human_operator("Testing...", sys.argv[1])

    else:
        reporter = ErrorReporter()
        reporter.report()
