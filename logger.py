import logging
from logging.config import fileConfig

from decouple import config


__all__ = ['logger']


SMTP_HANDLER = 1


fileConfig('./logging_config.ini')
logger = logging.getLogger('bot')
logger.handlers[SMTP_HANDLER].fromaddr = config('LOGGER_EMAIL')
logger.handlers[SMTP_HANDLER].toaddrs = [
    email.strip() for email in config('DEV_EMAILS').split(',')
]
