import logging
from datetime import datetime

from decouple import config
from telegram import ChatAction, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, TimedOut, Unauthorized)
from telegram.ext import CallbackQueryHandler, CommandHandler, Updater

from bot import utils
from bot.db import MongoBackend
from bot.integration import JiraBackend
import .commands import as commands


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
        commands.MainMenuCommandFactory,
        commands.MenuCommandFactory,
        commands.AuthCommandFactory
    ]

    def __init__(self):
        self.__updater = Updater(config('BOT_TOKEN'))
        self.__issue_cache = dict()

        self.__db = MongoBackend()
        self.__jira = JiraBackend()

        self.__updater.dispatcher.add_handler(
            CommandHandler('start', self.__start_command)
        )

        self.__updater.dispatcher.add_handler(
            CommandHandler('help', self.__help_command)
        )

        self.__updater.dispatcher.add_handler(
            CallbackQueryHandler(self.__tracking_handler, pattern=r'^tracking:')
        )
        self.__updater.dispatcher.add_handler(
            CallbackQueryHandler(
                self.__get_project_issues,
                pattern=r'^project:'
            )
        )
        self.__updater.dispatcher.add_handler(
            CallbackQueryHandler(
                self.__choose_status,
                pattern=r'^project_s_menu:'
            )
        )
        self.__updater.dispatcher.add_handler(
            CallbackQueryHandler(
                self.__get_project_status_issues,
                pattern=r'^project_s:'
            )
        )
        self.__updater.dispatcher.add_handler(
            CallbackQueryHandler(
                self.__paginator_handler,
                pattern=r'^paginator:'
            )
        )
        self.__updater.dispatcher.add_error_handler(self.__error_callback)

        # TODO: create all commands from commands_factories
        for command in self.commands_factories:
            self.__updater.dispatcher.add_handler(command(self).command_callback())

    def start(self):
        self.__updater.start_polling()
        self.__updater.idle()

    @staticmethod
    def __start_command(bot, update):
        first_name = update.message.from_user.first_name
        message = 'Hi, {}! List of basic commands can look through /help. '
        'Be sure to specify your credentials using the '
        'command /authorization.'

        bot.send_message(
            chat_id=update.message.chat_id,
            text=message.format(first_name),
        )

    def __paginator_handler(self, bot, update):
        """
        After the user clicked on the page number to be displayed, the handler
        generates a message with the data from the specified page, creates
        a new keyboard and modifies the last message (the one under which
        the key with the page number was pressed)
        """
        scope = self.__get_query_scope(update)
        key, page = self.__get_issue_data(scope['data'])
        user_data = self.__issue_cache.get(key)

        if not user_data:
            logging.info('There is no data in the cache for {}'.format(key))
            return

        str_key = 'paginator:{}'.format(key)
        buttons = utils.get_pagination_keyboard(
            current=page,
            max_page=user_data['page_count'],
            str_key=str_key + '-{}'
        )
        formatted_issues = '\n\n'.join(user_data['issues'][page - 1])

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
        )

    def __get_project_status_issues(self, bot, update):
        """
        Call order: /menu > Issues > Open project issues >
                    > Some project  > Some status
        Shows project issues with selected status
        """
        buttons = None
        scope = self.__get_query_scope(update)
        project_key = scope['data'].replace('project_s:', '')
        project, status = project_key.split(':')

        credentials, message = self.__get_and_check_cred(scope['telegram_id'])

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        issues, status_code = self.__jira.get_project_status_issues(
            project=project,
            status=status,
            username=credentials.get('username'),
            password=credentials.get('password')
        )

        if not issues:
            bot.edit_message_text(
                text="Project {} doesn't have any "
                     "issues with {} status".format(project, status),
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        if len(issues) < self.issues_per_page:
            formatted_issues = '\n\n'.join(issues)
        else:
            project_issues = utils.split_by_pages(issues, self.issues_per_page)
            page_count = len(project_issues)
            self.__issue_cache[project_key] = dict(
                issues=project_issues, page_count=page_count
            )

            # return the first page
            formatted_issues = '\n\n'.join(project_issues[0])
            str_key = 'paginator:{name}'.format(name=project_key)
            buttons = utils.get_pagination_keyboard(
                current=1,
                max_page=page_count,
                str_key=str_key + '-{}'
            )

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
        )

    def __tracking_handler(self, bot, update):
        """
        Call order: /menu > Tracking > Any option
        """
        scope = self.__get_query_scope(update)

        if 'tracking:my' in scope['data']:
            data = scope['data'].replace('tracking:my', '')
            date = self.__choose_date(bot, data, scope, 'tracking:my:{}')

            if date:
                # TODO: implement show time in this date
                bot.edit_message_text(
                    chat_id=scope['chat_id'],
                    message_id=scope['message_id'],
                    text='You chose: {day}.{month}.{year}'.format(**date),
                )

    def __choose_date(self, bot, data: str, scope: dict, pattern: str) -> dict:
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
            self.__show_calendar(bot, scope, int(year), int(month), pattern)

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
            self.__show_calendar(bot, scope, now.year, now.month, pattern)

    @staticmethod
    def __get_query_scope(update) -> dict:
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
    def __get_issue_data(query_data: str) -> (str, int):
        """
        Gets key and page for cached issues
        :param query_data: 'paginator:IHB-13'
        :return: ('IHB', 13)
        """
        _data = query_data.replace('paginator:', '')
        key, page = _data.split('-')

        return key, int(page)

    def __show_calendar(self, bot, scope: dict,
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

    def __get_and_check_cred(self, telegram_id: str):
        """
        Gets the user's credentials from the database and
        checks them (tries to authorize the user in JIRA)
        :param telegram_id: user id telegram
        :return: credentials and an empty message or False and an error message
        """
        credentials = self.__db.get_user_credentials(telegram_id)

        if credentials:
            username = credentials.get('username')
            password = utils.decrypt_password(credentials.get('password'))

            confirmed, status_code = self.__jira.check_credentials(
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
        except Unauthorized:
            pass
        except BadRequest as e:
            logging.error('{}'.format(e))
        except TimedOut as e:
            logging.error('{}'.format(e))
        except NetworkError as e:
            logging.error('{}'.format(e))
        except ChatMigrated as e:
            pass
        except TelegramError:
            pass
