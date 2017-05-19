import logging

from decouple import config
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
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
        
    /help
        Returns commands and its descriptions 
    """

    bot_commands = [
        '/start - Start to work with user',
        '/caps <some text> - Return entered text into uppercase',
        '/authorization <username> <password> - Save or update user '
        'credentials into DB',
        '/menu - Displaying menu with main functions',
        '/help - Returns commands and its descriptions'
    ]

    def __init__(self):
        self.updater = Updater(config('BOT_TOKEN'))
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
            CallbackQueryHandler(self._issues_handler, pattern=r'^issues:')
        )
        self.updater.dispatcher.add_handler(
            CommandHandler('help', self._help_command)
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
        bot.send_message(
            chat_id=update.message.chat_id,
            text='Test',
        )

    def _authorization_command(self, bot, update, args):
        username = None
        password = None
        telegram_id = str(update.message.from_user.id)

        try:
            username, password = args
        except ValueError:
            bot.send_message(
                chat_id=update.message.chat_id,
                text='Incorrectly entered data (enter only the username '
                     'and password separated by a space)'
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
        :param bot: 
        :param update: 
        :return: 
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
                             text='You chosed tracking',
                             reply_markup=reply_markup)
            return

        bot.send_message(chat_id=update.message.chat_id,
                         text=update.message.text)

    def _issues_menu(self, bot, update):
        """
        Call order: /menu > Issues
        :param bot: 
        :param update: 
        :return: 
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
        :param bot: 
        :param update: 
        :return: 
        """
        query = update.callback_query
        bot.edit_message_text(
            text='You chose: {}'.format(query.data.replace('issues:', '')),
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

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
