from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from common import utils

from .base import AbstractCommand


class DisconnectMenuCommand(AbstractCommand):
    positive_answer = 'Yes'
    negative_answer = 'No'

    def handler(self, bot, update, *args, **kwargs):
        """
        /disconnect
        """
        button_list = [
            InlineKeyboardButton(
                'Yes', callback_data='disconnect:{}'.format(self.positive_answer)
            ),
            InlineKeyboardButton(
                'No', callback_data='disconnect:{}'.format(self.negative_answer)
            ),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text='Are you sure you want to log out? All credentials associated with this user will be lost.',
            reply_markup=reply_markup
        )
