import logging

import pendulum
from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory
from .issue import UserUnresolvedIssuesCommand
from .menu import ChooseDeveloperMenuCommand, ChooseProjectMenuCommand


class ShowCalendarCommand(AbstractCommand):

    def handler(self, bot, scope, date, pattern, selected_day, *args, **kwargs):
        """Displays a calendar (inline keyboard)"""
        calendar = utils.create_calendar(date, pattern + ':{}', selected_day)

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Choose start date & end date',
            reply_markup=calendar
        )


class ChooseDateIntervalCommand(AbstractCommand):

    def handler(self, bot, scope, selected_day=None, *args, **kwargs):
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
            ShowCalendarCommand(self._bot_instance).handler(bot, scope, selected_date, pattern, selected_day)
        else:
            now = pendulum.now()
            ShowCalendarCommand(self._bot_instance).handler(bot, scope, now, scope['data'], selected_day)


class TrackingUserWorklogCommand(AbstractCommand):
    templates = {
        'user_content': '<a href="{issue_permalink}">{issue_key}</a> {time_spent}\n{date}',
        'project_content': '<a href="{issue_permalink}">{issue_key}</a> <b>{author_displayName}</b> '
                           '{time_spent}\n{date}',
        'time_spent': 'All time spent from <b>{}</b> to <b>{}</b>: <b>{}h</b>',
    }

    def report_data(self, log, template='user_content') -> str:
        """Generates a message for report"""
        date = utils.to_human_date(log.get('created'))
        return self.templates.get(template).format(**log, date=date)

    def calculate_total_time(self, seconds: int, start_date: str, end_date: str) -> str:
        """Calculates time spent for issues in time interval"""
        hours = 0
        hour_in_seconds = 3600

        try:
            hours = seconds / hour_in_seconds
        except TypeError:
            logging.warning('Seconds are not a numeric type: {} {}'.format(type(seconds), seconds))

        return self.templates.get('time_spent').format(start_date, end_date, round(hours, 2))

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """Shows all worklog of the user in selected date interval"""
        start_date = utils.to_datetime(scope['start_date'], scope['user_d_format'])
        end_date = utils.to_datetime(scope['end_date'], scope['user_d_format'])
        end_date = utils.add_time(end_date, hours=23, minutes=59)
        user_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='End date can not be less than the start date',
            )
            return

        all_worklogs, status_code = self._bot_instance.jira.get_all_user_worklogs(
            scope['start_date'], scope['end_date'], **credentials
        )
        all_user_logs = self._bot_instance.jira.get_user_worklogs(
            all_worklogs, credentials['username'], name_key='author_name'
        )

        # comparison of the time interval (the time of the log should be between the start and end dates)
        seconds = 0
        for log in sorted(all_user_logs, key=lambda x: x.get('created')):
            logged_time = log.get('created')

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(self.report_data(log))
                seconds += log.get('time_spent_seconds')

        key = '{telegram_id}:{username}:{start_date}:{end_date}'.format(**scope, username=credentials['username'])
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
        end_date = utils.add_time(end_date, hours=23, minutes=59)
        project_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='End date can not be less than the start date',
            )
            return

        all_worklogs, status_code = self._bot_instance.jira.get_project_worklogs(
            scope.get('project'), scope.get('start_date'), scope.get('end_date'), **credentials
        )

        # comparison of the time interval (the time of the log should be between the start and end dates)
        seconds = 0
        for log in sorted(all_worklogs, key=lambda x: x.get('created')):
            logged_time = log.get('created')

            if (start_date <= logged_time) and (logged_time <= end_date):
                project_worklogs.append(
                    TrackingUserWorklogCommand(self._bot_instance).report_data(log, template='project_content')
                )
                seconds += log.get('time_spent_seconds')

        key = '{telegram_id}:{project}:{start_date}:{end_date}'.format(**scope)
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
            TrackingUserWorklogCommand(self._bot_instance).calculate_total_time(
                seconds,
                scope['start_date'],
                scope['end_date']
            ),
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
        end_date = utils.add_time(end_date, hours=23, minutes=59)
        user_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='End date can not be less than the start date',
            )
            return

        all_worklogs, status_code = self._bot_instance.jira.get_user_project_worklogs(
            scope.get('user'), scope.get('project'), scope.get('start_date'), scope.get('end_date'), **credentials
        )
        all_user_logs = self._bot_instance.jira.get_user_worklogs(
            all_worklogs, scope.get('user'), name_key='author_displayName'
        )

        # comparison of the time interval (the time of the log should be between the start and end dates)
        seconds = 0
        for log in sorted(all_user_logs, key=lambda x: x.get('created')):
            logged_time = log.get('created')

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(
                    TrackingUserWorklogCommand(self._bot_instance).report_data(log)
                )
                seconds += log.get('time_spent_seconds')

        key = '{telegram_id}:{username}:{project}:{start_date}:{end_date}'.format(**scope, username=scope.get('user'))
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
            TrackingUserWorklogCommand(self._bot_instance).calculate_total_time(
                seconds,
                scope['start_date'],
                scope['end_date']
            ),
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
        selected_day = None

        cmd_scope = scope.get('data').split(':')

        # attempt to get the first selected date (to visually highlight it)
        try:
            if cmd_scope[1] and cmd_scope[1] not in change_month:
                selected_day = cmd_scope[1]
        except IndexError:
            pass
        else:
            if selected_day:
                _date = [int(numb) for numb in selected_day.split('-')]
                selected_day = pendulum.create(*_date)

        # choice of time interval
        if change_month in scope['data']:
            ChooseDateIntervalCommand(self._bot_instance).handler(bot, scope, selected_day)
            return

        if len(cmd_scope) != 3:  # must be [cmd, start_date, end_date]
            ChooseDateIntervalCommand(self._bot_instance).handler(bot, scope, selected_day)
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
                'jira_d_format': utils.JIRA_DATE_FORMAT,
                'user_d_format': utils.USER_DATE_FORMAT
            }
        )

        if isinstance(obj, TrackingUserWorklogCommand):
            bot.edit_message_text(
                text='Please wait, your request is processing',
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
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
                'jira_d_format': utils.JIRA_DATE_FORMAT,
                'user_d_format': utils.USER_DATE_FORMAT,
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

        if isinstance(obj, (TrackingProjectWorklogCommand, TrackingProjectUserWorklogCommand)):
            bot.edit_message_text(
                text='Please wait, your request is processing',
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )

        _pattern = 'tproject_u:{start_date}:{end_date}:{project}'.format(**scope) + ':{}'
        obj.handler(bot, scope, credentials, pattern=_pattern, footer='tracking-pu')

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tproject')
