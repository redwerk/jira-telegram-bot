import logging
from logging.config import fileConfig
from logging.handlers import SMTPHandler

from decouple import config

import bot
from bot.utils import emit

fileConfig('logging_config.ini')
logger = logging.getLogger()

SMTPHandler.emit = emit

email_error_handler = SMTPHandler(
    mailhost=(config('SMTP_HOST'), config('SMTP_PORT', cast=int)),
    fromaddr='robot@redwer.com',
    toaddrs=config('DEV_EMAILS').split(', '),
    subject='JTB ERRORS',
    credentials=(config('SMTP_USER'), config('SMTP_PASS')),
)
email_fomatter = logger.handlers[0].formatter
email_error_handler.setFormatter(email_fomatter)
logger.addHandler(email_error_handler)


if __name__ == '__main__':
    bot_obj = bot.JiraBot()
    logging.info('Starting bot')
    bot_obj.start()
