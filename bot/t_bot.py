import logging

from decouple import config
from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, TimedOut, Unauthorized)
from telegram.ext import CommandHandler, Updater

import bot.commands as commands
from bot import utils
from bot.db import MongoBackend
from bot.integration import JiraBackend


class JiraBot:
    """
    Bot to integrate with the JIRA service.

    Commands (synopsis and description):
    /start
        Start to work with user
    /oauth
        Authorizing via OAuth
    /logout
        Deleted user credentials from DB
    /menu
        Displaying menu with main functions
    /help
        Returns commands and its descriptions
    """

    bot_commands = [
        '/start - Start to work with user',
        '/menu - Displays menu with main functions',
        '/oauth - Authorizing via OAuth',
        '/logout - Deleted user credentials from DB',
        '/help - Returns commands and its descriptions'
    ]
    issues_per_page = 10
    commands_factories = [
        commands.IssueCommandFactory,
        commands.ProjectIssuesFactory,
        commands.IssuesPaginatorFactory,
        commands.MainMenuCommandFactory,
        commands.MenuCommandFactory,
        commands.OAuthMenuCommandFactory,
        commands.OAuthCommandFactory,
        commands.LogoutMenuCommandFactory,
        commands.LogoutCommandFactory,
        commands.TrackingCommandFactory,
        commands.TrackingProjectCommandFactory,
    ]

    def __init__(self):
        self.__updater = Updater(config('BOT_TOKEN'), workers=2)
        self.issue_cache = dict()

        self.db = MongoBackend()
        self.jira = JiraBackend()

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
        message = 'Hi, {}! You can see the list of commands using /help. ' \
                  'Please, enter your credentials using /auth.\n\n'.format(first_name)

        bot.send_message(
            chat_id=update.message.chat_id,
            text=message + '\n'.join(self.bot_commands),
        )

    @staticmethod
    def get_query_scope(update) -> dict:
        """
        Gets scope data for current message
        """
        telegram_id = str(update.callback_query.from_user.id)

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
        _data = query_data.replace('paginator:', '')
        key, page = _data.split('#')

        return key, int(page)

    def get_and_check_cred(self, telegram_id: str):
        """
        Gets the user's credentials from the database and
        checks them (tries to authorize the user in JIRA)
        :param telegram_id: user id telegram
        :return: credentials and an empty message or False and an error message
        """
        credentials = self.db.get_user_credentials(telegram_id)

        if credentials:
            confirmed, status_code = self.jira.check_credentials(credentials)

            if not confirmed:
                return False, self.jira.login_error.get(status_code, 'Credentials are incorrect')

            return credentials, ''

        return False, "You didn't enter credentials"

    def save_into_cache(self, data: list, key: str):
        """
        Creating a pagination list. Saving into a cache for further work with
        it without redundant requests to JIRA.

        If strings less than value per page just return a formatted string without buttons.
        :param data: list of strings
        :param key: key for stored it into cache dict
        :return: formatted string with pagination buttons
        """
        buttons = None

        if len(data) < self.issues_per_page:
            formatted_issues = '\n\n'.join(data)
        else:
            splitted_data = utils.split_by_pages(data, self.issues_per_page)
            page_count = len(splitted_data)
            self.issue_cache[key] = dict(
                issues=splitted_data, page_count=page_count
            )

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
        except (Unauthorized, BadRequest, TimedOut, NetworkError, ChatMigrated, TelegramError) as e:
            logging.error('{}'.format(e))
