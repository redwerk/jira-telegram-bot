import logging

from decouple import config
from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, TimedOut, Unauthorized)
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from bot import utils
from bot.db import MongoBackend
from bot.integration import JiraBackend


class JiraBot(object):
    """
    Bot to integrate with the JIRA service.
    
    Commands (synopsis and description):
    /start  
        Start to work with user
    /caps <some text>
        Return entered text into uppercase 
    /authorization <username> <password> 
        Save or update user credentials into DB
    /help
        Returns commands and its descriptions 
    """

    bot_commands = [
        '/start - Start to work with user',
        '/caps <some text> - Return entered text into uppercase',
        '/authorization <username> <password> - Save or update user '
        'credentials into DB',
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
            CommandHandler('caps', self._caps_command, pass_args=True)
        )
        self.updater.dispatcher.add_handler(
            CommandHandler('help', self._help_command)
        )
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.text, self._echo_command)
        )
        self.updater.dispatcher.add_error_handler(self._error_callback)

    def start(self):
        self.updater.start_polling()
        self.updater.idle()

    def stop(self):
        self.updater.stop()

    def _start_command(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text="I'm a bot, please talk to me!")

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

    def _echo_command(self, bot, update):
        logging.info('Echo: {}'.format(update.message.text))
        bot.send_message(chat_id=update.message.chat_id,
                         text=update.message.text)

    def _caps_command(self, bot, update, args):
        text_caps = ' '.join(args).upper()
        bot.send_message(chat_id=update.message.chat_id, text=text_caps)

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
