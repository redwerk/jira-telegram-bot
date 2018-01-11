import argparse

from logger import * # noqa


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
