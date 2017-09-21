import logging
from collections import namedtuple

from decouple import config
from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, Unauthorized)
from telegram.ext import CommandHandler, Updater

import bot.commands as commands
from bot import utils
from bot.db import MongoBackend
from bot.integration import JiraBackend


class JiraBot:
    """Bot to integrate with the JIRA service"""

    bot_commands = [
        '/start - Starts the bot',
        '/menu - Displays options to interact with Jira',
        '/connect jira.yourcompany.com username password - Login into host using user/pass',
        '/oauth jira.yourcompany.com - Login into host using OAuth',
        '/disconnect - Deletes user credentials from DB',
        '/help - Returns commands and its descriptions'
    ]
    issues_per_page = 10
    commands_factories = [
        commands.IssueCommandFactory,
        commands.ProjectIssuesFactory,
        commands.ContentPaginatorFactory,
        commands.MainMenuCommandFactory,
        commands.MenuCommandFactory,
        commands.OAuthCommandFactory,
        commands.DisconnectMenuCommandFactory,
        commands.DisconnectCommandFactory,
        commands.TrackingCommandFactory,
        commands.TrackingProjectCommandFactory,
        commands.OAuthLoginCommandFactory,
        commands.BasicLoginCommandFactory,
        commands.AddHostProcessCommandFactory,
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
            CommandHandler('help', self.__help_command)
        )

        self.__updater.dispatcher.add_error_handler(self.__error_callback)

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
                'allowed_hosts': list()
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

    @staticmethod
    def get_issue_data(query_data: str) -> (str, int):
        """
        Gets key and page for cached issues
        :param query_data: 'paginator:IHB#13'
        :return: ('IHB', 13)
        """
        data = query_data.replace('paginator:', '')
        key, page = data.split('#')

        return key, int(page)

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
            return False, 'You are not authorized by any of the methods (user/pass or OAuth)'

        else:
            if auth_method == 'basic':
                credentials = (
                    user_data.get('username'),
                    utils.decrypt_password(user_data.get('auth')['basic']['password'])
                )
            else:
                host_data = self.db.get_host_data(user_data.get('host_url'))

                if not host_data:
                    return False, 'In database there are no data on the {} host'.format(user_data.get('host_url'))

                credentials = {
                    'access_token': user_data.get('auth')['oauth']['access_token'],
                    'access_token_secret': user_data.get('auth')['oauth']['access_token_secret'],
                    'consumer_key': host_data.get('consumer_key'),
                    'key_cert': utils.read_rsa_key(config('PRIVATE_KEY_PATH'))
                }

            auth_data = self.AuthData(auth_method, user_data.get('host_url'), user_data.get('username'), credentials)
            status = self.jira.check_authorization(
                auth_data.auth_method,
                auth_data.jira_host,
                auth_data.credentials,
                base_check=True
            )

            if status:
                return auth_data, 'Success'
            else:
                return False, 'Invalid credentials, please authorize again'

    def save_into_cache(self, data: list, key: str):
        """
        Creating a pagination list. Saving into a cache for further work with
        it without redundant requests to JIRA.

        If strings less than value per page just return a formatted string without buttons.
        :param data: list of strings
        :param key: key for stored it into cache collection
        :return: formatted string with pagination buttons
        """
        buttons = None

        if len(data) < self.issues_per_page + 1:
            formatted_issues = '\n\n'.join(data)
        else:
            splitted_data = utils.split_by_pages(data, self.issues_per_page)
            page_count = len(splitted_data)
            status = self.db.create_cache(key, splitted_data, page_count)

            if not status:
                logging.exception('An attempt to write content to the cache failed: {}'.format(key))

            # return the first page
            formatted_issues = '\n\n'.join(splitted_data[0])
            str_key = 'paginator:{}'.format(key)
            buttons = utils.get_pagination_keyboard(
                current=1,
                max_page=page_count,
                str_key=str_key + '#{}'
            )

        return formatted_issues, buttons

    def __help_command(self, bot, update):
        bot.send_message(
            chat_id=update.message.chat_id, text='\n'.join(self.bot_commands)
        )

    @staticmethod
    def __error_callback(bot, update, error):
        try:
            raise error
        except (Unauthorized, BadRequest, NetworkError, ChatMigrated, TelegramError) as e:
            logging.exception('{}'.format(e))
