from decouple import config
from telegram.ext import CallbackQueryHandler, CommandHandler

from .base import AbstractCommand, AbstractCommandFactory
from .menu import ChooseJiraHostMenuCommand, LogoutMenuCommand


class OAuthMenuCommandFactory(AbstractCommandFactory):
    """
    /oauth - displays supported JIRA hosts for further authorization
    """
    def command(self, bot, update, *args, **kwargs):
        ChooseJiraHostMenuCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('oauth', self.command)


class UserOAuthCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Command generates URL for further authorization via Flask OAuth service"""
        scope = self._bot_instance.get_query_scope(update)
        host_url = scope['data'].replace('oauth:', '')
        host = self._bot_instance.db.get_host_data(host_url)

        service_url = '{}/authorize/{}/?host={}'.format(config('OAUTH_SERVICE_URL'), scope['telegram_id'], host['url'])

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Follow the link to confirm authorization\n{}'.format(service_url),
        )


class OAuthCommandFactory(AbstractCommandFactory):
    def command(self, bot, update, *args, **kwargs):
        UserOAuthCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^oauth:')


class LogoutMenuCommandFactory(AbstractCommandFactory):
    """
    /logout - request to delete credentials from the database
    """
    def command(self, bot, update, *args, **kwargs):
        LogoutMenuCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('logout', self.command)


class LogoutCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Deletes user credentials from DB"""
        scope = self._bot_instance.get_query_scope(update)
        answer = scope['data'].replace('logout:', '')

        if answer == 'y':
            status = self._bot_instance.db.delete_user(scope['telegram_id'])

            if status:
                bot.edit_message_text(
                    chat_id=scope['chat_id'],
                    message_id=scope['message_id'],
                    text='User successfully deleted from database',
                )
                return
            else:
                bot.edit_message_text(
                    chat_id=scope['chat_id'],
                    message_id=scope['message_id'],
                    text='The user was not removed from the database, please try again later.',
                )
                return

        else:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='Deleting user is not confirmed',
            )
            return


class LogoutCommandFactory(AbstractCommandFactory):
    def command(self, bot, update, *args, **kwargs):
        LogoutCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^logout:')
