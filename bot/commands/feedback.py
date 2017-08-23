from decouple import config
from telegram import ParseMode
from telegram.ext import CommandHandler

from bot.commands.base import AbstractCommand, AbstractCommandFactory
from bot.utils import (generate_email_message, get_email_address,
                       get_text_without_email, send_email)


class FeedbackMessageCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Gets feedback from the user. Generates a letter and sends it to the recipient"""
        chat_id = update.message.chat_id
        message = 'Thanks for your feedback!'
        raw_feedback = update.message.text.replace('/feedback', '').strip()

        if not raw_feedback:
            return

        emails = get_email_address(raw_feedback)
        email_text = get_text_without_email(raw_feedback)

        email_message = generate_email_message(
            sender_email=emails,
            recipient_email=config('FEEDBACK_RECIPIENT'),
            subject='JTB Feedback',
            message=email_text
        )
        success = send_email(email_message)

        if not success:
            message = 'Your feedback was not sent. Please try again later.'

        bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.HTML
        )


class FeedbackMessageCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        FeedbackMessageCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('feedback', self.command, pass_args=True)
