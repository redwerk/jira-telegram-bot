from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import utils
from bot.commands.auth import UserOAuthCommand
from bot.commands.base import AbstractCommand, AbstractCommandFactory


class AddHostCommand(AbstractCommand):
    negative_answer = 'No'

    def handler(self, bot, update, *args, **kwargs):
        """
        Adds a new host into a system. If a host is already in DB - returns a link for authorizing via Flask service.
        If not - request for adding a new host into DB.
        """
        chat_id = update.message.chat_id
        data = kwargs.get('args')[0]

        if not data:
            return

        host_exists = self._bot_instance.db.get_host_data(data)

        if host_exists:
            message = 'Follow the link to confirm authorization\n{}'.format(
                UserOAuthCommand.generate_auth_link(telegram_id=chat_id, host_url=host_exists.get('url'))
            )
            bot.send_message(
                chat_id=chat_id,
                text=message,
            )
        else:
            button_list = [
                InlineKeyboardButton(
                    'Yes', callback_data='add_host:{}'.format(data)
                ),
                InlineKeyboardButton(
                    'No', callback_data='add_host:{}'.format(self.negative_answer)
                ),
            ]

            reply_markup = InlineKeyboardMarkup(utils.build_menu(
                button_list, n_cols=2
            ))

            bot.send_message(
                chat_id=chat_id,
                text='This host is not supported at this time, '
                     'do you want to go through the procedure of adding a new host?',
                reply_markup=reply_markup
            )


class AddHostCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        AddHostCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('add_host', self.command, pass_args=True)


class AddHostProcessCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        Validates Jira host URL, generates RSA-key pairs, saves  keys into server,
        returns consumer key, public key and link on Flask OAuth service
        """
        # TODO: regex for validate host url
        # TODO: verify the validity of the jira host
        # TODO: generating RSA-key pairs
        # TODO: saving key pairs into the server
        # TODO: creates a new record in the host collection
        scope = self._bot_instance.get_query_scope(update)
        host_url = scope['data'].replace('add_host:', '')

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Host: {}'.format(host_url),
        )


class AddHostProcessCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        AddHostProcessCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^add_host:')
