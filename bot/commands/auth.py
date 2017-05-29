from telegram.ext import CommandHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class UserAuthenticatedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwatgs):
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

            jira_cred = dict(username=username, password=encrypted_password)
            user_data = dict(telegram_id=telegram_id, jira=jira_cred)

            # create user or update his credentials
            transaction_status = self._bot_instance.__db.save_credentials(user_data)

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


class AuthCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        UserAuthenticatedCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('authorization', self.command, pass_args=True)
