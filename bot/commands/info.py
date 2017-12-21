import logging

from telegram.ext import CommandHandler

from .base import AbstractCommand


class HelpCommand(AbstractCommand):
    """/help - returns help description"""
    description = [
        '/start - Starts the bot',
        '/listunresolved - Shows different issues',
        '/liststatus - Shows users and projects issues with a selected status',
        '/filter - Shows issues by favourite filters',
        '/time - Shows spented time of issue, user or project',
        '/schedule - create new schedule command',
        '/unschedule - remove command from schedule list',
        '/connect jira.yourcompany.com username password - Login into host using user/pass',
        '/oauth jira.yourcompany.com - Login into host using OAuth',
        '/disconnect - Deletes user credentials from DB',
        '/help - Returns commands and its descriptions'
    ]

    def handler(self, bot, update, *args, **kwargs):
        bot.send_message(
            chat_id=update.message.chat_id,
            text='\n'.join(self.description)
        )

    def command_callback(self):
        return CommandHandler('help', self.handler)


class StartCommand(AbstractCommand):
    """/start - returns help description"""
    message = (
        'Hi, {}! Please, enter Jira host by typing \n'
        '/connect jira.yourcompany.com username password OR\n'
        '/oauth jira.yourcompany.com'
    )

    def handler(self, bot, update, *args, **kwargs):
        first_name = update.message.from_user.first_name
        message = self.message.format(first_name)

        telegram_id = update.message.from_user.id
        user_exists = self.app.db.is_user_exists(telegram_id)

        if not user_exists:
            data = {
                'telegram_id': telegram_id,
                'host_url': None,
                'username': None,
                'auth_method': None,
                'auth': {
                    'oauth': dict(access_token=None, access_token_secret=None),
                    'basic': dict(password=None),
                },
            }

            transaction_status = self.app.db.create_user(data)
            if not transaction_status:
                logging.exception(
                    'Error while creating a new user via '
                    '/start command, username: {}'.format(update.message.from_user.username)
                )

        bot.send_message(chat_id=update.message.chat_id, text=message)

    def command_callback(self):
        return CommandHandler('start', self.handler)
