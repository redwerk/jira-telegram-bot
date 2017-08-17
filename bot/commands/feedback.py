import os

from decouple import config
from telegram import ParseMode
from telegram.ext import CommandHandler, Filters, MessageHandler

from bot.commands.base import AbstractCommand, AbstractCommandFactory
from bot.utils import check_email_address, generate_email_message, send_email


class FeedbackMessageCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Sends a help message with feedback instructions to user"""
        chat_id = update.message.chat_id
        with open(os.path.join(config('DOCS_PATH'), 'help_email.txt')) as file:
            message = file.read()

        bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.HTML
        )

        return


class FeedbackMessageCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        FeedbackMessageCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('feedback', self.command)


class SendFeedbackToEmailCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        Gets feedback from the user. Validates the e-mail address.
        Generates a letter and sends it to the recipient
        """
        message = 'Thanks for your feedback!'
        raw_text = update.message.text
        chat_id = update.message.chat_id

        email, *splitted_text = raw_text.split('\n\n')
        email = email.strip()

        valid_email = check_email_address(email)

        if valid_email:
            email_message = generate_email_message(
                sender_email=email,
                recipient_email=config('FEEDBACK_RECIPIENT'),
                subject='JTB Feedback',
                message='\n'.join(splitted_text)
            )
            success = send_email(
                config('SMTP_HOST'),
                config('SMTP_PORT', cast=int),
                config('SMTP_USER'),
                config('SMTP_PASS'),
                email_message
            )

            if not success:
                message = 'A letter with your feedback was not sent. Please try again later.'
        else:
            message = 'You specified the email address in an invalid format. See /feedback for more information.'

        bot.send_message(chat_id=chat_id, text=message)
        return


class SendFeedbackToEmailCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        SendFeedbackToEmailCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return MessageHandler(Filters.text, self.command, pass_user_data=True)
