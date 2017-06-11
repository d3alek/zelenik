import logging

class Logger:
    def __init__(self, name, level=logging.INFO):
        logging.basicConfig(level=level)
        self.name = name
        self.level = level
        self.logger = logging.getLogger(name)

    def of(self, method_name):
        return Logger(".".join([self.name, method_name]), level=self.level)

    def info(self, message):
        self.logger.info("%s" % message)

    def error(self, message, traceback=False):
        self.logger.error("%s" % message, exc_info=traceback)


