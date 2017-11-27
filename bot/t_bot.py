import logging
from collections import namedtuple

from decouple import config
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import CommandHandler, Updater

import bot.commands as commands
from bot.commands.base import SendMessageFactory
from bot.integration import JiraBackend
from common import utils
from common.db import MongoBackend
from common.exceptions import BaseJTBException, BotAuthError


class JiraBot:
    """Bot to integrate with the JIRA service"""

    bot_commands = [
        '/start - Starts the bot',
        '/listunresolved - Shows different issues',
        '/filter - shows issues by favourite filters',
        '/connect jira.yourcompany.com username password - Login into host using user/pass',
        '/oauth jira.yourcompany.com - Login into host using OAuth',
        '/disconnect - Deletes user credentials from DB',
        '/help - Returns commands and its descriptions'
    ]
    issues_per_page = 10
    commands_factories = [
        commands.ListUnresolvedIssuesCommand,
        commands.FilterDispatcherCommand,
        commands.FilterIssuesCommand,
        commands.BasicLoginCommand,
        commands.OAuthLoginCommand,
        commands.DisconnectMenuCommand,
        commands.DisconnectCommand,
        commands.ContentPaginatorCommand,
    ]

    def __init__(self):
        self.__updater = Updater(config('BOT_TOKEN'), workers=config('WORKERS', cast=int, default=3))

        self.db = MongoBackend()
        self.jira = JiraBackend()
        self.AuthData = namedtuple('AuthData', 'auth_method jira_host username credentials')

        self.__updater.dispatcher.add_handler(
            CommandHandler('start', self.start_command)
        )

        self.__updater.dispatcher.add_handler(
            CommandHandler('help', self.help_command)
        )

        self.__updater.dispatcher.add_error_handler(self.error_callback)

        for command in self.commands_factories:
            cb = command(self).command_callback()
            self.__updater.dispatcher.add_handler(cb)

    def start(self):
        self.__updater.start_polling()
        self.__updater.idle()

    def start_command(self, bot, update):
        first_name = update.message.from_user.first_name
        message = 'Hi, {}! Please, enter Jira host by typing \n' \
                  '/connect jira.yourcompany.com username password OR\n' \
                  '/oauth jira.yourcompany.com'.format(first_name)

        telegram_id = update.message.from_user.id
        user_exists = self.db.is_user_exists(telegram_id)

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
            transaction_status = self.db.create_user(data)

            if not transaction_status:
                logging.exception(
                    'Error while creating a new user via '
                    '/start command, username: {}'.format(update.message.from_user.username)
                )

        bot.send_message(
            chat_id=update.message.chat_id,
            text=message
        )

    @staticmethod
    def get_query_scope(update) -> dict:
        """
        Gets scope data for current message
        """
        telegram_id = update.callback_query.from_user.id

        query = update.callback_query
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        data = query.data

        return dict(
            telegram_id=telegram_id,
            chat_id=chat_id,
            message_id=message_id,
            data=data
        )

    def get_and_check_cred(self, telegram_id: int):
        """
        Gets the user data and tries to log in according to the specified authorization method.
        Output of messages according to missing information
        :param telegram_id: user id telegram
        :return: returns a namedtuple for further authorization or bool and messages
        """
        user_data = self.db.get_user_data(telegram_id)
        auth_method = user_data.get('auth_method')

        if not auth_method:
            raise BotAuthError('You are not authorized by any of the methods (user/pass or OAuth)')

        else:
            if auth_method == 'basic':
                credentials = (
                    user_data.get('username'),
                    utils.decrypt_password(user_data.get('auth')['basic']['password'])
                )
            else:
                host_data = self.db.get_host_data(user_data.get('host_url'))

                if not host_data:
                    raise BotAuthError(
                        'In database there are no data on the {} host'.format(user_data.get('host_url'))
                    )

                credentials = {
                    'access_token': user_data.get('auth')['oauth']['access_token'],
                    'access_token_secret': user_data.get('auth')['oauth']['access_token_secret'],
                    'consumer_key': host_data.get('consumer_key'),
                    'key_cert': utils.read_rsa_key(config('PRIVATE_KEY_PATH'))
                }

            auth_data = self.AuthData(auth_method, user_data.get('host_url'), user_data.get('username'), credentials)
            self.jira.check_authorization(
                auth_data.auth_method,
                auth_data.jira_host,
                auth_data.credentials,
                base_check=True
            )

            return auth_data

    def help_command(self, bot, update):
        bot.send_message(
            chat_id=update.message.chat_id, text='\n'.join(self.bot_commands)
        )

    def error_callback(self, bot, update, error):
        try:
            raise error
        except BaseJTBException as e:
            SendMessageFactory.send(bot, update, text=e.message, simple_message=True)
        except TimedOut:
            pass
        except (NetworkError, TelegramError) as e:
            logging.exception('{}'.format(e))
