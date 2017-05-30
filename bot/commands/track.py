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

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """Shows all worklog of the user in selected date interval"""
        start_date = utils.to_datetime(scope['start_date'], scope['user_d_format'])
        end_date = utils.to_datetime(scope['end_date'], scope['user_d_format'])
        user_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='The end date can not be less than the start date',
            )
            return

        issues, status_code = self._bot_instance.jira.get_tracking_issues(
            username=credentials['username'], password=credentials['password']
        )
        issues_ids = self._bot_instance.jira.get_issues_id(issues)
        all_worklogs, status_code = self._bot_instance.jira.get_issues_worklogs(
            issues_ids, username=credentials['username'], password=credentials['password']
        )
        user_logs = self._bot_instance.jira.get_user_worklogs(all_worklogs, credentials['username'])

        # comparison of the time interval (the time of the log should be between the start and end dates)
        for log in user_logs:
            logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(
                    '{} {}\n{}'.format(issues_ids[log.issueId], log.timeSpent, log.created)
                )

        start_line = 'User work log from {start_date} to {end_date}\n\n'.format(**scope)
        if user_worklogs:
            formatted = '\n\n'.join(user_worklogs)
        else:
            formatted = 'No data about worklogs in this time interval'

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=start_line + formatted,
        )


class TrackingProjectWorklogCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """Shows all worklogs by selected project in selected date interval"""
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='You chose: show tracking time of selected project',
        )


class TrackingProjectUserWorklogCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
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
        jira_date_format = '%Y-%m-%dT%H:%M:%S.%f%z'
        user_date_format = '%Y-%m-%d'
        scope = self._bot_instance.get_query_scope(update)

        # choice of time interval
        if change_month in scope['data']:
            ChooseDateIntervalCommand(self._bot_instance).handler(bot, scope)
            return

        cmd_scope = scope['data'].split(':')

        if len(cmd_scope) != 3:  # must be [cmd, start_date, end_date]
            ChooseDateIntervalCommand(self._bot_instance).handler(bot, scope)
            return

        credentials, message = self._bot_instance.get_and_check_cred(
            scope['telegram_id']
        )

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        obj = self._command_factory_method(cmd_scope[0])
        scope.update(
            {
                'start_date': cmd_scope[1],
                'end_date': cmd_scope[2],
                'jira_d_format': jira_date_format,
                'user_d_format': user_date_format
            }
        )
        obj.handler(bot, scope, credentials)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tracking')
