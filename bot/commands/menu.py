from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class MainMenuCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
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


class IssuesMenuCommand(AbstractCommand):

    def handler(self, bot, scope):
        issues_button_list = [
            InlineKeyboardButton('My unresolved', callback_data='issues:my'),
            InlineKeyboardButton('Unresolved by projects', callback_data='issues:p'),
            InlineKeyboardButton('By project with a status', callback_data='issues:ps'),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(issues_button_list, n_cols=2))

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='What issues do you want to see?',
            reply_markup=reply_markup
        )


class TrackingMenuCommand(AbstractCommand):

    def handler(self, bot, scope):
        tracking_button_list = [
            InlineKeyboardButton('My time', callback_data='tracking:my'),
            InlineKeyboardButton('Project time', callback_data='tracking:p'),
            InlineKeyboardButton('Project time by user', callback_data='tracking:pu')
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(tracking_button_list, n_cols=2))

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='What kind of time do you want to see?',
            reply_markup=reply_markup
        )


class MainMenuCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        MainMenuCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('menu', self.command)


class MenuCommandFactory(AbstractCommandFactory):

    commands = {
        "issues_menu": IssuesMenuCommand,
        "tracking_menu": TrackingMenuCommand
    }

    def command(self, bot, update, *args, **kwargs):
        scope = self._bot_instance.get_query_scope(update)
        obj = self._command_factory_method(scope['data'])
        obj.handler(bot, scope)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'.+_menu$')
