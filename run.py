import logging
from logging.config import fileConfig

from decouple import config

import bot

fileConfig('logging_config.ini')


if __name__ == '__main__':
    db_obj = bot.MongoBackend()
    bot_obj = bot.JiraBot(
        bot_token=config('BOT_TOKEN')
    )
    a = db_obj.get_user_credential('208810129')

    logging.info('Starting bot')
    bot_obj.start()
