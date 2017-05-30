import logging
from datetime import datetime

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
    /authorization <username> <password>
        Save or update user credentials into DB
    /menu
        Displaying menu with main functions
    /help
        Returns commands and its descriptions
    """

    bot_commands = [
        '/start - Start to work with user',
        '/authorization <username> <password> - Save or update user '
        'credentials into DB',
        '/menu - Displaying menu with main functions',
        '/help - Returns commands and its descriptions'
    ]
    issues_per_page = 10
    commands_factories = [
        commands.IssueCommandFactory,
        commands.ProjectIssuesFactory,
        commands.IssuesPaginatorFactory,
        commands.MainMenuCommandFactory,
        commands.MenuCommandFactory,
        commands.AuthCommandFactory,
        commands.TrackingCommandFactory,
    ]

    def __init__(self):
        self.__updater = Updater(config('BOT_TOKEN'))
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

    @staticmethod
    def start_command(bot, update):
        first_name = update.message.from_user.first_name
        message = 'Hi, {}! List of basic commands can look through /help. '
        'Be sure to specify your credentials using the '
        'command /authorization.'

        bot.send_message(
            chat_id=update.message.chat_id,
            text=message.format(first_name),
        )

    def choose_date(self, bot, data: str, scope: dict, pattern: str) -> dict:
        """
        Show calendar. User can change a month or choose the date.
        :param data: callback data
        :param scope: current message data
        :param pattern: callback pattern
        """
        now = datetime.now()

        # user wants to change the month
        if 'change_m' in data:
            month, year = data.replace(':change_m:', '').split('.')
            self.show_calendar(bot, scope, int(year), int(month), pattern)

        # user was selected the date
        elif 'date' in scope['data']:
            date = data.replace(':date:', '')
            day, month, year = date.split('.')

            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='You chose: {}'.format(data.replace(':date:', '')),
            )

            return dict(day=int(day), month=int(month), year=int(year))

        else:
            self.show_calendar(bot, scope, now.year, now.month, pattern)

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
        :param query_data: 'paginator:IHB-13'
        :return: ('IHB', 13)
        """
        _data = query_data.replace('paginator:', '')
        key, page = _data.split('-')

        return key, int(page)

    def show_calendar(self, bot, scope: dict,
                      year: int, month: int, pattern: str) -> None:
        """
        Shows calendar with selected month and year
        :param scope: current message data
        :param year:
        :param month:
        :param pattern: callback data
        """
        calendar = utils.create_calendar(year, month, pattern)

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Choose a date',
            reply_markup=calendar
        )

    def get_and_check_cred(self, telegram_id: str):
        """
        Gets the user's credentials from the database and
        checks them (tries to authorize the user in JIRA)
        :param telegram_id: user id telegram
        :return: credentials and an empty message or False and an error message
        """
        credentials = self.db.get_user_credentials(telegram_id)

        if credentials:
            username = credentials.get('username')
            password = utils.decrypt_password(credentials.get('password'))

            confirmed, status_code = self.jira.check_credentials(
                username, password
            )

            if not confirmed:
                return False, 'Credentials are incorrect'

            return dict(username=username, password=password), ''

        return False, 'You did not specify credentials'

    def __help_command(self, bot, update):
        bot.send_message(
            chat_id=update.message.chat_id, text='\n'.join(self.bot_commands)
        )

    @staticmethod
    def __error_callback(bot, update, error):
        try:
            raise error
        except Unauthorized as e:
            logging.error('{}'.format(e))
        except BadRequest as e:
            logging.error('{}'.format(e))
        except TimedOut as e:
            logging.error('{}'.format(e))
        except NetworkError as e:
            logging.error('{}'.format(e))
        except ChatMigrated as e:
            logging.error('{}'.format(e))
        except TelegramError as e:
            logging.error('{}'.format(e))
