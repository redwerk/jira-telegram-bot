import logging
from logging.config import fileConfig
from logging.handlers import SMTPHandler

from decouple import config

import bot

fileConfig('logging_config.ini')
logger = logging.getLogger()

email_error_handler = SMTPHandler(
    mailhost='localhost',
    fromaddr='root@jirabot.redwer.com',
    toaddrs=[email.strip() for email in config('DEV_EMAILS').split(',')],
    subject='JTB ERRORS',
)
email_fomatter = logger.handlers[0].formatter
email_error_handler.setFormatter(email_fomatter)
logger.addHandler(email_error_handler)


if __name__ == '__main__':
    bot_obj = bot.JiraBot()
    logging.info('Starting bot')
    bot_obj.start()
