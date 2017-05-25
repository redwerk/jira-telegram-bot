import logging
from logging.config import fileConfig

import bot

fileConfig('logging_config.ini')


if __name__ == '__main__':
    bot_obj = bot.JiraBot()
    logging.info('Starting bot')
    bot_obj.start()
