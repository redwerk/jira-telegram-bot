import argparse
import logging
from logging.config import fileConfig

from decouple import config


STREAM_HANDLER_NUMB = 0
SMTP_HANDLER_NUMB = 1

fileConfig('logging_config.ini')
logger = logging.getLogger()
logger.handlers[STREAM_HANDLER_NUMB].fromaddr = config('LOGGER_EMAIL')
logger.handlers[SMTP_HANDLER_NUMB].toaddrs = [email.strip() for email in config('DEV_EMAILS').split(',')]


def run_bot():
    from bot.app import JTBApp
    app = JTBApp()
    app.start()


def run_web():
    from web.app import app
    app.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run bot or web application.')
    parser.add_argument('app', choices=['bot', 'web'])
    args = parser.parse_args()
    if args.app == "bot":
        run_bot()
    elif args.app == "web":
        run_web()
