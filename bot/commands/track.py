from datetime import datetime

from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class ShowCalendarCommand(AbstractCommand):

    def handler(self, bot, scope, year, month, pattern, *args, **kwargs):
        """Displays a calendar (inline keyboard)"""
        calendar = utils.create_calendar(int(year), int(month), pattern + ':{}')

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Choose a date',
            reply_markup=calendar
        )


class ChooseDateIntervalCommand(AbstractCommand):

    def handler(self, bot, scope, *args, **kwargs):
        """
        The choice of the time interval. Is called in two stages -
        to select start and end dates
        """
        change_month = ':change_m:'

        # user wants to change the month
        if change_month in scope['data']:
            pattern, date = scope['data'].split(change_month)
            month, year = date.split('.')
            ShowCalendarCommand(self._bot_instance).handler(bot, scope, year, month, pattern)
        else:
            now = datetime.now()
            ShowCalendarCommand(self._bot_instance).handler(bot, scope, now.year, now.month, scope['data'])


class TrackingUserWorklogCommand(AbstractCommand):

    def handler(self, bot, scope, *args, **kwargs):
        """Shows all worklog of the user in selected date interval"""
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='You chose: {start_date} {end_date}'.format(**scope),
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
        change_month = ':change_m:'
        scope = self._bot_instance.get_query_scope(update)

        # choice of time interval
        if change_month in scope['data']:
            ChooseDateIntervalCommand(self._bot_instance).handler(bot, scope)
            return

        cmd_scope = scope['data'].split(':')

        if len(cmd_scope) != 3:  # must be [cmd, start_date, end_date]
            ChooseDateIntervalCommand(self._bot_instance).handler(bot, scope)
            return

        obj = self._command_factory_method(cmd_scope[0])
        scope.update({'start_date': cmd_scope[1], 'end_date': cmd_scope[2]})
        obj.handler(bot, scope)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tracking')
