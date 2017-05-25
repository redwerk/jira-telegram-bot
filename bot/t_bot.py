import logging

from decouple import config
from telegram import ChatAction, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, TimedOut, Unauthorized)
from telegram.ext import CallbackQueryHandler, CommandHandler, Updater

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

    def __init__(self):
        self.__updater = Updater(config('BOT_TOKEN'))
        self.__issue_cache = dict()

        self.__db = MongoBackend()
        self.__jira = JiraBackend()

        self.__updater.dispatcher.add_handler(
            CommandHandler('start', self.__start_command)
        )
        self.__updater.dispatcher.add_handler(
            CommandHandler(
                'authorization',
                self.__authorization_command,
                pass_args=True)
        )
        self.__updater.dispatcher.add_handler(
            CommandHandler('menu', self.__menu_command)
        )
        self.__updater.dispatcher.add_handler(
            CommandHandler('help', self.__help_command)
        )
        self.__updater.dispatcher.add_handler(
            CallbackQueryHandler(self.__menu_dispatcher, pattern=r'.+_menu$')
        )
        self.__updater.dispatcher.add_handler(
            CallbackQueryHandler(self.__issues_handler, pattern=r'^issues:')
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

    def __authorization_command(self, bot, update, args):
        """
        /authorization <username> <password>
        
        Saving user credentials. Credentials are verified through user 
        authorization, if validation is completed, data is saved.
        
        :return: Error message or message about successful saving of data
        """
        username = None
        password = None
        telegram_id = str(update.message.from_user.id)

        try:
            username, password = args
        except ValueError:
            bot.send_message(
                chat_id=update.message.chat_id,
                text='Incorrectly entered data (use the following '
                     'command format: /authorization <username> <password>)'
            )
        else:
            # Verification of credentials. The data will be stored only
            # if there is confirmed authorization in Jira.
            confirmed, status_code = self.__jira.check_credentials(
                username, password
            )

            if not confirmed:
                message = self.__jira.login_error.get(
                    status_code, 'Unknown error'
                )
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text=message
                )
                return

            encrypted_password = utils.encrypt_password(password)

            jira_cred = dict(username=username, password=encrypted_password)
            user_data = dict(telegram_id=telegram_id, jira=jira_cred)

            # create user or update his credentials
            transaction_status = self.__db.save_credentials(user_data)

            if not transaction_status:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text='Internal error. Please try again after some time.'
                )
            else:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text='Your credentials are saved successfully.\n'
                         'Please, delete all messages which contains your '
                         'credentials (even if the credentials are incorrect).'
                )

    def __menu_command(self, bot, update):
        """
        Call order: /menu
        """
        button_list = [
            InlineKeyboardButton(
                'Issues', callback_data='issues_menu'
            ),
            InlineKeyboardButton(
                'Tracking', callback_data='tracking_menu'
            ),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text='What do you want to see?',
            reply_markup=reply_markup
        )

    def __menu_dispatcher(self, bot, update):
        """
        Call order: /menu > Any option
        """
        scope = self.__get_query_scope(update)
        issues_button_list = [
            InlineKeyboardButton(
                'My unresolved', callback_data='issues:my'
            ),
            InlineKeyboardButton(
                'Unresolved by projects', callback_data='issues:p'
            ),
            InlineKeyboardButton(
                'By project with a status', callback_data='issues:ps'
            ),
        ]

        if 'issues_menu' == scope['data']:
            reply_markup = InlineKeyboardMarkup(utils.build_menu(
                issues_button_list, n_cols=2
            ))

            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='What issues do you want to see?',
                reply_markup=reply_markup
            )
            return

    def __issues_handler(self, bot, update):
        """
        Call order: /menu > Issues > Any option
        """
        scope = self.__get_query_scope(update)

        # Show user unresolved issues
        if scope['data'] == 'issues:my':
            self.__get_user_unresolved_issues(
                bot,
                scope['telegram_id'],
                scope['chat_id'],
                scope['message_id']
            )
            return

        # Show unresolved issues by project
        elif scope['data'] == 'issues:p':
            self.__choose_project(
                bot,
                scope['telegram_id'],
                scope['chat_id'],
                scope['message_id']
            )
            return

        # Show unresolved issues by project with a status
        elif scope['data'] == 'issues:ps':
            self.__choose_project(
                bot,
                scope['telegram_id'],
                scope['chat_id'],
                scope['message_id'],
                status=True
            )
            return

    def __get_user_unresolved_issues(self, bot, telegram_id,
                                     chat_id, message_id):
        """
        Receiving open user issues and modifying the current message
        :param bot: 
        :param telegram_id: user id
        :param chat_id: chat id with user
        :param message_id: last message id
        :return: Message with a list of open user issues
        """
        bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        credentials, message = self.__get_and_check_cred(telegram_id)

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=chat_id,
                message_id=message_id
            )
            return

        username = credentials.get('username')
        password = credentials.get('password')

        issues, status = self.__jira.get_open_issues(
            username=username, password=password
        )

        if not issues:
            bot.edit_message_text(
                text='You have no unresolved issues',
                chat_id=chat_id,
                message_id=message_id
            )
            return

        buttons = None
        if len(issues) < self.issues_per_page:
            formatted_issues = '\n\n'.join(issues)
        else:
            user_issues = utils.split_by_pages(issues, self.issues_per_page)
            page_count = len(user_issues)
            self.__issue_cache[username] = dict(
                issues=user_issues, page_count=page_count
            )

            # return the first page
            formatted_issues = '\n\n'.join(user_issues[0])
            str_key = 'paginator:{}'.format(username)
            buttons = utils.get_pagination_keyboard(
                current=1,
                max_page=page_count,
                str_key=str_key + '-{}'
            )

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=buttons
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

    def __choose_project(self, bot, telegram_id,
                         chat_id, message_id, status=None):
        """
        Call order: /menu > Issues > Unresolved by project
        Displaying inline keyboard with names of projects
        
        :param bot: 
        :param telegram_id: user id in telegram
        :param chat_id: current chat whith a user
        :param message_id: last message
        """
        credentials, message = self.__get_and_check_cred(telegram_id)

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=chat_id,
                message_id=message_id
            )
            return

        username = credentials.get('username')
        password = credentials.get('password')

        projects_buttons = list()
        projects, status_code = self.__jira.get_projects(
            username=username, password=password
        )

        if not projects:
            bot.edit_message_text(
                text="Sorry, can't get projects",
                chat_id=chat_id,
                message_id=message_id
            )
            return

        if status:
            _callback = 'project_s_menu:{}'
        else:
            _callback = 'project:{}'

        # dynamic keyboard creation
        for project_name in projects:
            projects_buttons.append(
                InlineKeyboardButton(
                    text=project_name,
                    callback_data=_callback.format(project_name)
                )
            )

        footer_button = [
            InlineKeyboardButton('« Back', callback_data='issues_menu')
        ]
        buttons = InlineKeyboardMarkup(
            utils.build_menu(
                projects_buttons,
                n_cols=3,
                footer_buttons=footer_button)
        )

        bot.edit_message_text(
            text='Choose one of the projects',
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=buttons
        )

    def __get_project_issues(self, bot, update):
        """
        Call order: /menu > Issues > Open project issues > Some project
        Shows unresolved issues by selected project
        """
        buttons = None
        scope = self.__get_query_scope(update)
        project_name = scope['data'].replace('project:', '')

        credentials, message = self.__get_and_check_cred(scope['telegram_id'])

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        issues, status_code = self.__jira.get_open_project_issues(
            project=project_name,
            username=credentials.get('username'),
            password=credentials.get('password')
        )

        if not issues:
            bot.edit_message_text(
                text="Project doesn't have any open issues",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return
        
        if len(issues) < self.issues_per_page:
            formatted_issues = '\n\n'.join(issues)
        else:
            project_issues = utils.split_by_pages(issues, self.issues_per_page)
            page_count = len(project_issues)
            self.__issue_cache[project_name] = dict(
                issues=project_issues, page_count=page_count
            )

            # return the first page
            formatted_issues = '\n\n'.join(project_issues[0])
            str_key = 'paginator:{name}'.format(name=project_name)
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

    def __choose_status(self, bot, update):
        """
        Call order: /menu > Issues > Unresolved by project > Some project
        Displaying inline keyboard with available statuses
        """
        scope = self.__get_query_scope(update)
        project_name = scope['data'].replace('project_s_menu:', '')

        credentials, message = self.__get_and_check_cred(scope['telegram_id'])

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        username = credentials.get('username')
        password = credentials.get('password')

        status_buttons = list()
        statuses, status = self.__jira.get_statuses(
            username=username, password=password
        )

        if not statuses:
            bot.edit_message_text(
                text="Sorry, can't get statuses at this moment",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        for _status in statuses:
            status_buttons.append(
                InlineKeyboardButton(
                    text=_status,
                    callback_data='project_s:{}:{}'.format(
                        project_name, _status
                    )
                )
            )
        footer_button = [
            InlineKeyboardButton('« Back', callback_data='issues:ps')
        ]

        buttons = InlineKeyboardMarkup(
            utils.build_menu(
                status_buttons,
                n_cols=2,
                footer_buttons=footer_button)
        )

        text = 'You chose {} project.\n' \
               'Choose one of the statuses'.format(project_name)
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=text,
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
