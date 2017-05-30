from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class ChooseDateIntervalCommand(AbstractCommand):
    def handler(self, *args, **kwargs):
        pass


class TrackingUserWorklogCommand(AbstractCommand):
    def handler(self, bot, scope, *args, **kwargs):
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='You chose: show my tracking time',
        )


class TrackingProjectWorklogCommand(AbstractCommand):
    def handler(self, bot, scope, *args, **kwargs):
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='You chose: show tracking time of selected project',
        )


class TrackingProjectUserWorklogCommand(AbstractCommand):
    def handler(self, bot, scope, *args, **kwargs):
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='You chose: show tracking time by project and user',
        )


class TrackingCommandFactory(AbstractCommandFactory):
    commands = {
        'tracking-my': TrackingUserWorklogCommand,
        'tracking-p': TrackingProjectWorklogCommand,
        'tracking-pu': TrackingProjectUserWorklogCommand,
    }

    def command(self, bot, update, *args, **kwargs):
        scope = self._bot_instance.get_query_scope(update)
        obj = self._command_factory_method(scope['data'])
        obj.handler(bot, scope)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tracking')
