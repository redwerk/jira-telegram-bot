import logging
from logging.config import fileConfig

from decouple import config


__all__ = ['logger']


STREAM_HANDLER_NUMB = 0
SMTP_HANDLER_NUMB = 1

fileConfig('./logging_config.ini')
logger = logging.getLogger('bot')
logger.handlers[STREAM_HANDLER_NUMB].fromaddr = config('LOGGER_EMAIL')
logger.handlers[SMTP_HANDLER_NUMB].toaddrs = [email.strip() for email in config('DEV_EMAILS').split(',')]
