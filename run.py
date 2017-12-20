import logging
from logging.config import fileConfig

from decouple import config

from bot.app import JTBApp

StreamHandlerNumb = 0
SMTPHandlerNumb = 1

fileConfig('logging_config.ini')
logger = logging.getLogger()
logger.handlers[SMTPHandlerNumb].fromaddr = config('LOGGER_EMAIL')
logger.handlers[SMTPHandlerNumb].toaddrs = [email.strip() for email in config('DEV_EMAILS').split(',')]

if __name__ == '__main__':
    app = JTBApp()
    app.start()
