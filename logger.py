import logging
from logging.config import dictConfig

from decouple import config


__all__ = ['logger']


log_level = 'DEBUG' if config('DEBUG', cast=bool) else 'INFO'

dictConfig(
    {
        'version': 1,
        'formatters': {
            'default': {
                'format': '[%(asctime)s: %(levelname)s] %(filename)s:%(lineno)d: %(message)s',
            }},
        'handlers': {
            'email': {
                'class': "utils.logging_handlers.MailAdminHandler",
                'level': 'ERROR',
                'mailhost': (config('LOGGER_EMAIL_HOST'), config('LOGGER_EMAIL_PORT')),
                'fromaddr': config('LOGGER_EMAIL'),
                'toaddrs': config('DEV_EMAILS', cast=lambda v: [s.strip() for s in v.split(',')]),
                'subject': '',
                'formatter': 'default'
            },
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'default'
            },
            'root_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': log_level,
                'formatter': 'default',
                'filename': 'logs/main.log',
                'when': 'midnight',
                'backupCount': 100,
            },
            'webhooks_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': log_level,
                'formatter': 'default',
                'filename': 'logs/webhooks.log',
                'when': 'midnight',
                'backupCount': 100,
            }
        },
        'loggers': {
            '': {
                'level': log_level,
                'handlers': ['console', 'root_file', 'email']
             },
            'bot': {
                'level': log_level,
                'handlers': ['console', 'root_file', 'email']
            },
            'werkzeug': {
                'level': log_level,
                'handlers': ['console', 'webhooks_file', 'email'],
                'qualname': 'werkzeug'
            }
        }
    }
)

logger = logging.getLogger('bot')
