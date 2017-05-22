import logging

from decouple import config
from telegram import (ChatAction, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, TimedOut, Unauthorized)
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, Updater)

from bot import utils
from bot.db import MongoBackend
from bot.integration import JiraBackend


class JiraBot(object):
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

    def __init__(self):
        self.updater = Updater(config('BOT_TOKEN'))
        self._user_open_issues = dict()
        self.issues_per_page = 10

        self._db = MongoBackend()
        self._jira = JiraBackend()

        self.updater.dispatcher.add_handler(
            CommandHandler('start', self._start_command)
        )
        self.updater.dispatcher.add_handler(
            CommandHandler(
                'authorization',
                self._authorization_command,
                pass_args=True)
        )
        self.updater.dispatcher.add_handler(
            CommandHandler('menu', self._menu_command)
        )
        self.updater.dispatcher.add_handler(
            CommandHandler('help', self._help_command)
        )
        self.updater.dispatcher.add_handler(
            CallbackQueryHandler(self._issues_handler, pattern=r'^issues:')
        )
        self.updater.dispatcher.add_handler(
            CallbackQueryHandler(
                self._my_issue_paginator_handler,
                pattern=r'^my_i:'
            )
        )
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.text, self._menu_dispatcher)
        )
        self.updater.dispatcher.add_error_handler(self._error_callback)

        menu_keyboard = [
            ['Issues', 'Tracking'],
        ]

        self.menu_markup = ReplyKeyboardMarkup(
            menu_keyboard, one_time_keyboard=True
        )

    def start(self):
        self.updater.start_polling()
        self.updater.idle()

    def stop(self):
        self.updater.stop()

    def _start_command(self, bot, update):
        first_name = update.message.from_user.first_name
        message = 'Hi, {}! List of basic commands can look through /help. '
        'Be sure to specify your credentials using the '
        'command /authorization.'

        bot.send_message(
            chat_id=update.message.chat_id,
            text=message.format(first_name),
        )

    def _authorization_command(self, bot, update, args):
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
            confirmed, status_code = self._jira.check_credentials(
                username, password
            )

            if not confirmed:
                message = self._jira.login_error.get(
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
            transaction_status = self._db.save_credentials(user_data)

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

    def _menu_command(self, bot, update):
        bot.send_message(
            chat_id=update.message.chat_id,
            text='What do you want to see?',
            reply_markup=self.menu_markup
        )

    def _menu_dispatcher(self, bot, update):
        """
        Call order: /menu
        """
        logging.info('Echo: {}'.format(update.message.text))
        reply_markup = ReplyKeyboardRemove()

        if 'Issues' == update.message.text:
            bot.send_message(chat_id=update.message.chat_id,
                             text='Issues menu',
                             reply_markup=reply_markup)
            self._issues_menu(bot, update)
            return
        elif 'Tracking' == update.message.text:
            bot.send_message(chat_id=update.message.chat_id,
                             text='Tracking menu',
                             reply_markup=reply_markup)
            return

        bot.send_message(chat_id=update.message.chat_id,
                         text=update.message.text)

    def _issues_menu(self, bot, update):
        """
        Call order: /menu > Issues
        """
        issues_button_list = [
            InlineKeyboardButton(
                'My open issues', callback_data='issues:my'
            ),
            InlineKeyboardButton(
                'Open issues by projects', callback_data='issues:p'
            ),
            InlineKeyboardButton(
                'Open issues by project and status', callback_data='issues:ps'
            ),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            issues_button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text='Chose from options',
            reply_markup=reply_markup
        )

    def _issues_handler(self, bot, update):
        """
        Call order: /menu > Issues > Any option
        """
        query = update.callback_query
        telegram_id = str(update.callback_query.from_user.id)
        chat_id = query.message.chat_id
        message_id = query.message.message_id

        if query.data == 'issues:my':
            self._getting_my_open_issues(bot, telegram_id, chat_id, message_id)
            return

        bot.edit_message_text(
            text='You chose: {}'.format(query.data.replace('issues:', '')),
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

    def _getting_my_open_issues(self, bot, telegram_id, chat_id, message_id):
        """
        Receiving open user issues and modifying the current message
        :param bot: 
        :param telegram_id: user id
        :param chat_id: chat id with user
        :param message_id: last message id
        :return: Message with a list of open user issues
        """
        bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        credentials, message = self._get_and_check_cred(telegram_id)

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=chat_id,
                message_id=message_id
            )
            return

        username = credentials.get('username')
        password = credentials.get('password')

        issues, status = self._jira.get_open_issues(
            username=username, password=password
        )

        if not issues:
            bot.edit_message_text(
                text='You have no open issues',
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
            self._user_open_issues[username] = dict(
                issues=user_issues, page_count=page_count
            )

            # return the first page
            formatted_issues = '\n\n'.join(user_issues[0])
            buttons = utils.get_pagination_keyboard(1, page_count, 'my_i:{}')

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=buttons
        )

    def _my_issue_paginator_handler(self, bot, update):
        """
        After the user clicked on the page number to be displayed, the handler 
        generates a message with the data from the specified page, creates 
        a new keyboard and modifies the last message (the one under which 
        the key with the page number was pressed)
        """
        telegram_id = str(update.callback_query.from_user.id)

        query = update.callback_query
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        current_page = int(query.data.replace('my_i:', ''))

        user_cred = self._db.get_user_credentials(telegram_id)

        if not user_cred:
            bot.edit_message_text(
                text='You did not specify credentials',
                chat_id=chat_id,
                message_id=message_id
            )

        user_data = self._user_open_issues.get(user_cred['username'])
        buttons = utils.get_pagination_keyboard(
            current=current_page,
            max_page=user_data['page_count'],
            str_key='my_i:{}'
        )
        formatted_issues = '\n\n'.join(user_data['issues'][current_page - 1])

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=buttons
        )

    def _get_and_check_cred(self, telegram_id: str):
        """
        Gets the user's credentials from the database and 
        checks them (tries to authorize the user in JIRA)
        :param telegram_id: user id telegram 
        :return: credentials and an empty message or False and an error message
        """
        credentials = self._db.get_user_credentials(telegram_id)

        if credentials:
            username = credentials.get('username')
            password = utils.decrypt_password(credentials.get('password'))

            confirmed, status_code = self._jira.check_credentials(
                username, password
            )

            if not confirmed:
                return False, 'Credentials are incorrect'

            return dict(username=username, password=password), ''

        return False, 'You did not specify credentials'

    def _help_command(self, bot, update):
        bot.send_message(
            chat_id=update.message.chat_id, text='\n'.join(self.bot_commands)
        )

    def _error_callback(self, bot, update, error):
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
