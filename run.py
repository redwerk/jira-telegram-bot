import argparse

from logger import * # noqa
from bot.app import JTBApp
from web.app import app


def run_bot():
    telegram_bot = JTBApp()
    telegram_bot.start()


def run_web():
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run bot or web application.')
    parser.add_argument('app', choices=['bot', 'web'])
    args = parser.parse_args()
    if args.app == "bot":
        run_bot()
    elif args.app == "web":
        run_web()
