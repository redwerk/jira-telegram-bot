import logging

from decouple import config
from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, TimedOut, Unauthorized)
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from bot import MongoBackend
import utils


class JiraBot(MongoBackend):
    """
    Bot to integrate with the JIRA service.
    
    Commands (synopsis and description):
    /start  
        Start to work with user
    /caps <some text>
        Return entered text into uppercase 
    /authorization <username> <password> 
        Save user credentials into DB
    /update_credentials <username> <password> 
        Update user credentials into DB
    /help
        Returns commands and its descriptions 
    """

    bot_commands = [
        '/start - Start to work with user',
        '/caps <some text> - Return entered text into uppercase',
        '/authorization <username> <password> - Save user credentials into DB',
        '/update_credentials <username> <password> - '
        'Update user credentials into DB',
        '/help - Returns commands and its descriptions'
    ]

    def __init__(self):
        self.updater = Updater(config('BOT_TOKEN'))

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

        if self.get_user_data(telegram_id):
            bot.send_message(
                chat_id=update.message.chat_id,
                text="You're already authorized. If you want to change "
                     "credentials, use the "
                     "/update_credentials <username> <password>"
            )
            return

        try:
            username, password = args
        except ValueError:
            bot.send_message(
                chat_id=update.message.chat_id,
                text='Incorrectly entered data (enter only the username '
                     'and password separated by a space)'
            )
        else:
            encrypted_password = utils.encrypt_password(password)

            jira_cred = dict(username=username, password=encrypted_password)
            user_data = dict(telegram_id=telegram_id, jira=jira_cred)

            self.create_user(user_data)
            logging.info(
                'User {} was created successfully'.format(username)
            )

            bot.send_message(
                chat_id=update.message.chat_id,
                text='Your account info is saved successfully. '
                     'Now you can use the commands associated with '
                     'the service JIRA.'
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
