from decouple import config
from telegram.ext import CommandHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class UserAuthenticatedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        /auth <username> <password>

        Saving user credentials. Credentials are verified through user
        authorization, if validation is completed, data is saved.

        :return: Error message or message about successful saving of data
        """
        username = None
        password = None
        telegram_id = str(update.message.from_user.id)

        try:
            username, password = kwargs.get('args')
        except ValueError:
            bot.send_message(
                chat_id=update.message.chat_id,
                text='Incorrectly entered data. Use the following '
                     'command format:\n/auth <username> <password>'
            )
        else:
            bot.send_message(
                chat_id=update.message.chat_id,
                text='Processing, please wait...'
            )

            # Verification of credentials. The data will be stored only
            # if there is confirmed authorization in Jira.
            confirmed, status_code = self._bot_instance.jira.check_credentials(
                username, password
            )

            if not confirmed:
                message = self._bot_instance.jira.login_error.get(
                    status_code, 'Unknown error'
                )
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text=message
                )
                return

            encrypted_password = utils.encrypt_password(password)

            user_exists = self._bot_instance.db.is_user_exists(telegram_id)
            host_id = self._bot_instance.db.get_host_id(config('JIRA_HOST'))

            if not host_id:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text="Bot doesn't support working with this host: {}".format(config('JIRA_HOST'))
                )
                return

            transaction_status = None

            if user_exists:
                data = {
                    '{}.active'.format(host_id): True,
                    '{}.username'.format(host_id): username,
                    '{}.base.password'.format(host_id): encrypted_password
                }
                transaction_status = self._bot_instance.db.update_user(telegram_id, data)
            else:
                user_data = {
                    'telegram_id': telegram_id,
                    host_id: {
                        'active': True,
                        'username': username,
                        'base': {
                            'password': encrypted_password
                        }
                    }
                }

                # create a new user
                transaction_status = self._bot_instance.db.create_user(user_data)

            if not transaction_status:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text='Internal error. Please try again later.'
                )
            else:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text='Your credentials are saved successfully.\n'
                         'Please, delete all messages that contain your '
                         'credentials (even if they are incorrect).'
                )


class AuthCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        UserAuthenticatedCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('auth', self.command, pass_args=True)
