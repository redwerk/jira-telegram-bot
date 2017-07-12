import logging

import pendulum
from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory
from .issue import UserUnresolvedIssuesCommand
from .menu import ChooseDeveloperMenuCommand, ChooseProjectMenuCommand

JIRA_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
USER_DATE_FORMAT = '%Y-%m-%d'
ALLOWED_TIME_INTERVAL = 30


class ShowCalendarCommand(AbstractCommand):

    def handler(self, bot, scope, date, pattern, *args, **kwargs):
        """Displays a calendar (inline keyboard)"""
        calendar = utils.create_calendar(date, pattern + ':{}')

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Choose start date & end date',
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
            selected_date = pendulum.create(int(year), int(month))
            ShowCalendarCommand(self._bot_instance).handler(bot, scope, selected_date, pattern)
        else:
            now = pendulum.now()
            ShowCalendarCommand(self._bot_instance).handler(bot, scope, now, scope['data'])


class TrackingUserWorklogCommand(AbstractCommand):

    @staticmethod
    def report_data(log, logged_time, issues_ids, template='user') -> str:
        """Generates a message for report"""
        templates = {
            'user': '<a href="{permalink}">{key}</a> {time_spent}\n{date}',
            'project': '<a href="{permalink}">{key}</a> <b>{author}</b> {time_spent}\n{date}',
        }

        data = {
            'key': issues_ids[log.issueId].key,
            'time_spent': log.timeSpent,
            'permalink': issues_ids[log.issueId].permalink,
            'date': utils.to_human_date(logged_time),
            'author': log.author.displayName
        }

        return templates.get(template).format(**data)

    @staticmethod
    def calculate_total_time(seconds: int, start_date: str, end_date: str) -> str:
        """Calculates time spent for issues in time interval"""
        hours = 0
        hour_in_seconds = 3600

        try:
            hours = seconds / hour_in_seconds
        except TypeError:
            logging.warning('Seconds are not a numeric type: {} {}'.format(type(seconds), seconds))

        return 'All time spent from <b>{}</b> to <b>{}</b>: <b>{}h</b>'.format(start_date, end_date, round(hours, 2))

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """Shows all worklog of the user in selected date interval"""
        start_date = utils.to_datetime(scope['start_date'], scope['user_d_format'])
        end_date = utils.to_datetime(scope['end_date'], scope['user_d_format'])
        user_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='End date can not be less than the start date',
            )
            return

        issues_ids, status_code = self._bot_instance.jira.get_user_issues_by_worklog(
            scope['start_date'], scope['end_date'], **credentials
        )
        all_worklogs, status_code = self._bot_instance.jira.get_worklogs_by_id(issues_ids, **credentials)
        user_logs = self._bot_instance.jira.get_user_worklogs(all_worklogs, credentials['username'])

        # comparison of the time interval (the time of the log should be between the start and end dates)
        seconds = 0
        for log in user_logs:
            logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(
                    self.report_data(log, logged_time, issues_ids)
                )
                seconds += log.timeSpentSeconds

        key = '{username}:{start_date}:{end_date}'.format(**scope, username=credentials['username'])
        formatted, buttons = self._bot_instance.save_into_cache(user_worklogs, key)

        # title
        UserUnresolvedIssuesCommand.show_title(
            bot,
            'User worklog from <b>{start_date}</b> to <b>{end_date}</b>:'.format(**scope),
            scope['chat_id'],
            scope['message_id']
        )

        if not formatted and not buttons:
            message = 'No worklog data from <b>{start_date}</b> to <b>{end_date}</b>'.format(**scope)
            UserUnresolvedIssuesCommand.show_content(bot, message, scope['chat_id'])
            return

        # main content
        UserUnresolvedIssuesCommand.show_content(bot, formatted, scope['chat_id'], buttons)
        # all time
        UserUnresolvedIssuesCommand.show_content(
            bot,
            self.calculate_total_time(seconds, scope['start_date'], scope['end_date']),
            scope['chat_id'],
        )


class TrackingProjectWorklogCommand(AbstractCommand):

    def handler(self, bot, scope: dict, credentials: dict, *args, **kwargs):
        """Shows all worklogs by selected project in selected date interval"""
        start_date = utils.to_datetime(scope['start_date'], scope['user_d_format'])
        end_date = utils.to_datetime(scope['end_date'], scope['user_d_format'])
        project_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='End date can not be less than the start date',
            )
            return

        issues_ids, status_code = self._bot_instance.jira.get_project_issues_by_worklog(
            scope.get('project'), scope.get('start_date'), scope.get('end_date'), **credentials
        )
        all_worklogs, status_code = self._bot_instance.jira.get_worklogs_by_id(issues_ids, **credentials)

        # comparison of the time interval (the time of the log should be between the start and end dates)
        seconds = 0
        for i_log in all_worklogs:
            for log in i_log:
                logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

                if (start_date <= logged_time) and (logged_time <= end_date):
                    project_worklogs.append(
                        TrackingUserWorklogCommand.report_data(log, logged_time, issues_ids, template='project')
                    )
                    seconds += log.timeSpentSeconds

        key = '{project}:{start_date}:{end_date}'.format(**scope)
        formatted, buttons = self._bot_instance.save_into_cache(project_worklogs, key)

        # title
        UserUnresolvedIssuesCommand.show_title(
            bot,
            '<b>{project}</b> worklog from <b>{start_date}</b> to <b>{end_date}</b>:'.format(**scope),
            scope['chat_id'],
            scope['message_id']
        )

        if not formatted:
            message = 'No worklog data from <b>{start_date}</b> ' \
                      'to <b>{end_date}</b> on project <b>{project}</b>'.format(**scope)
            UserUnresolvedIssuesCommand.show_content(bot, message, scope['chat_id'])
            return

        # main content
        UserUnresolvedIssuesCommand.show_content(bot, formatted, scope['chat_id'], buttons)
        # all time
        UserUnresolvedIssuesCommand.show_content(
            bot,
            TrackingUserWorklogCommand.calculate_total_time(seconds, scope['start_date'], scope['end_date']),
            scope['chat_id'],
        )


class TrackingProjectUserWorklogCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Shows all worklogs by selected project for selected user
        in selected date interval
        """
        start_date = utils.to_datetime(scope['start_date'], scope['user_d_format'])
        end_date = utils.to_datetime(scope['end_date'], scope['user_d_format'])
        user_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='End date can not be less than the start date',
            )
            return

        issues_ids, status_code = self._bot_instance.jira.get_user_project_issues_by_worklog(
            scope.get('user'), scope.get('project'), scope.get('start_date'), scope.get('end_date'), **credentials
        )
        all_worklogs, status_code = self._bot_instance.jira.get_worklogs_by_id(issues_ids, **credentials)
        user_logs = self._bot_instance.jira.get_user_worklogs(all_worklogs, scope.get('user'), display_name=True)

        # comparison of the time interval (the time of the log should be between the start and end dates)
        seconds = 0
        for log in user_logs:
            logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(
                    TrackingUserWorklogCommand.report_data(log, logged_time, issues_ids)
                )
                seconds += log.timeSpentSeconds

        key = '{username}:{project}:{start_date}:{end_date}'.format(**scope, username=scope.get('user'))
        formatted, buttons = self._bot_instance.save_into_cache(user_worklogs, key)

        # title
        UserUnresolvedIssuesCommand.show_title(
            bot,
            '<b>{user}</b> worklog on <b>{project}</b> from <b>{start_date}</b> to <b>{end_date}</b>:'.format(**scope),
            scope['chat_id'],
            scope['message_id']
        )

        if not formatted:
            message = 'No worklog data about <b>{user}</b> from <b>{start_date}</b> ' \
                      'to <b>{end_date}</b> on project <b>{project}</b>'.format(**scope)
            UserUnresolvedIssuesCommand.show_content(bot, message, scope['chat_id'])
            return

        # main content
        UserUnresolvedIssuesCommand.show_content(bot, formatted, scope['chat_id'], buttons)
        # all time
        UserUnresolvedIssuesCommand.show_content(
            bot,
            TrackingUserWorklogCommand.calculate_total_time(seconds, scope['start_date'], scope['end_date']),
            scope['chat_id'],
        )


class TrackingCommandFactory(AbstractCommandFactory):

    commands = {
        'tracking-my': TrackingUserWorklogCommand,
        'tracking-p': ChooseProjectMenuCommand,
        'tracking-pu': ChooseProjectMenuCommand,
    }

    patterns = {
        'tracking-my': 'ignore',
        'tracking-p': 'tproject:{}',
        'tracking-pu': 'tproject_u_menu:{}',
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

        # date interval is limited
        start_date = utils.to_datetime(cmd_scope[1], USER_DATE_FORMAT)
        end_date = utils.to_datetime(cmd_scope[2], USER_DATE_FORMAT)
        date_interval = end_date - start_date

        if date_interval.days > ALLOWED_TIME_INTERVAL:
            bot.edit_message_text(
                text='The time interval is limited to {} days'.format(ALLOWED_TIME_INTERVAL),
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
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
                'jira_d_format': JIRA_DATE_FORMAT,
                'user_d_format': USER_DATE_FORMAT
            }
        )

        _pattern = self.patterns[cmd_scope[0]].format(cmd_scope[1] + ':' + cmd_scope[2] + ':{}')
        obj.handler(bot, scope, credentials, pattern=_pattern, footer='tracking_menu')

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tracking')


class TrackingProjectCommandFactory(AbstractCommandFactory):
    commands = {
        'tproject': TrackingProjectWorklogCommand,
        'tproject_u': TrackingProjectUserWorklogCommand,
        'tproject_u_menu': ChooseDeveloperMenuCommand,
    }

    def command(self, bot, update, *args, **kwargs):
        scope = self._bot_instance.get_query_scope(update)
        cmd, start_d, end_d, project, *user = scope['data'].split(':')

        if user:
            user = user[0]

        obj = self._command_factory_method(cmd)

        credentials, message = self._bot_instance.get_and_check_cred(scope['telegram_id'])
        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        scope.update(
            {
                'project': project,
                'start_date': start_d,
                'end_date': end_d,
                'jira_d_format': JIRA_DATE_FORMAT,
                'user_d_format': USER_DATE_FORMAT,
                'user': user
            }
        )

        # Protected feature. Only for users with administrator permissions
        if isinstance(obj, ChooseDeveloperMenuCommand):
            permission, status = self._bot_instance.jira.is_admin_permissions(**credentials)

            if not permission:
                message = 'You have no permissions to use this function'
                bot.edit_message_text(text=message, chat_id=scope['chat_id'], message_id=scope['message_id'])
                return

        _pattern = 'tproject_u:{start_date}:{end_date}:{project}'.format(**scope) + ':{}'
        obj.handler(bot, scope, credentials, pattern=_pattern, footer='tracking-pu')

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tproject')
