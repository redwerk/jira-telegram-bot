import logging

from decouple import config

import bot

handler = logging.StreamHandler()
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(pathname)s:%(lineno)d - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S %z'
)
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


if __name__ == '__main__':
    db_obj = bot.MongoBackend(
        logger=logger,
        server=config('DB_HOST'),
        port=config('DB_PORT', cast=int),
        db_name=config('DB_NAME'),
        collection=config('DB_COLLECTION')
    )
    bot_obj = bot.JiraBot(
        logger=logger,
        bot_token=config('BOT_TOKEN')
    )
    db_obj.get_user_credential('208810129')
    bot_obj.start()
