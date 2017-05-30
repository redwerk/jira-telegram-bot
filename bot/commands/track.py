from datetime import datetime

from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class ShowCalendarCommand(AbstractCommand):

    def handler(self, bot, scope, year, month, pattern, *args, **kwargs):
        """Displays a calendar (inline keyboard)"""
        calendar = utils.create_calendar(year, month, pattern)

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Choose a date',
            reply_markup=calendar
        )


class ChooseDateIntervalCommand(AbstractCommand):

    def handler(self, bot, scope, pattern, *args, **kwargs):
        """
        The choice of the time interval. Is called in two stages -
        to select start and end dates
        """
        now = datetime.now()
        data = scope['data']

        # user wants to change the month
        if 'change_m' in data:
            month, year = data.replace(':change_m:', '').split('.')
            ShowCalendarCommand(self._bot_instance).handler(
                bot, scope, int(year), int(month), pattern
            )

        # user was selected the date
        elif 'date' in scope['data']:
            date = data.replace(':date:', '')
            day, month, year = date.split('.')

            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='You chose: {}'.format(data.replace(':date:', '')),
            )

            return dict(day=int(day), month=int(month), year=int(year))

        else:
            ShowCalendarCommand(self._bot_instance).handler(
                bot, scope, now.year, now.month, pattern
            )


class TrackingUserWorklogCommand(AbstractCommand):

    def handler(self, bot, scope, *args, **kwargs):
        """Shows all worklog of the user in selected date interval"""
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='You chose: show my tracking time',
        )


class TrackingProjectWorklogCommand(AbstractCommand):

    def handler(self, bot, scope, *args, **kwargs):
        """Shows all worklogs by selected project in selected date interval"""
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='You chose: show tracking time of selected project',
        )


class TrackingProjectUserWorklogCommand(AbstractCommand):

    def handler(self, bot, scope, *args, **kwargs):
        """
        Shows all worklogs by selected project for selected user
        in selected date interval
        """
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
