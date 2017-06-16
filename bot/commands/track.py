from datetime import datetime

from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory
from .menu import ChooseDeveloperMenuCommand, ChooseProjectMenuCommand

JIRA_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
USER_DATE_FORMAT = '%Y-%m-%d'
ALLOWED_TIME_INTERVAL = 14


class ShowCalendarCommand(AbstractCommand):

    def handler(self, bot, scope, year, month, pattern, *args, **kwargs):
        """Displays a calendar (inline keyboard)"""
        calendar = utils.create_calendar(int(year), int(month), pattern + ':{}')

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
                text='End date can not be less than the start date',
            )
            return

        issues_ids, status_code = self._bot_instance.jira.get_user_issues_by_worklog(
            scope['start_date'], scope['end_date'], username=credentials['username'], password=credentials['password']
        )
        all_worklogs, status_code = self._bot_instance.jira.get_worklogs_by_id(
            issues_ids, username=credentials['username'], password=credentials['password']
        )
        user_logs = self._bot_instance.jira.get_user_worklogs(all_worklogs, credentials['username'])

        # comparison of the time interval (the time of the log should be between the start and end dates)
        for log in user_logs:
            logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(
                    '{} {}\n{}'.format(issues_ids[log.issueId], log.timeSpent, utils.to_human_date(logged_time))
                )

        start_line = 'User work log from {start_date} to {end_date}\n\n'.format(**scope)
        key = '{username}:{start_date}:{end_date}'.format(**scope, username=credentials['username'])
        formatted, buttons = self._bot_instance.save_into_cache(user_worklogs, key)

        if not formatted:
            text = start_line + 'No worklog data in chosen time interval'
        else:
            text = start_line + formatted

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=text,
            reply_markup=buttons
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
            scope.get('project'), scope.get('start_date'), scope.get('end_date'),
            username=credentials.get('username'), password=credentials.get('password')
        )
        all_worklogs, status_code = self._bot_instance.jira.get_worklogs_by_id(
            issues_ids, username=credentials['username'], password=credentials['password']
        )

        # comparison of the time interval (the time of the log should be between the start and end dates)
        for i_log in all_worklogs:
            for log in i_log:
                logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

                if (start_date <= logged_time) and (logged_time <= end_date):
                    project_worklogs.append(
                        '{} {} {}\n{}'.format(
                            issues_ids[log.issueId], log.author.displayName,
                            log.timeSpent, utils.to_human_date(logged_time)
                        )
                    )

        start_line = '{project} worklog from {start_date} to {end_date}\n\n'.format(**scope)
        key = '{project}:{start_date}:{end_date}'.format(**scope)
        formatted, buttons = self._bot_instance.save_into_cache(project_worklogs, key)

        if not formatted:
            text = start_line + 'No worklog data in chosen time interval'
        else:
            text = start_line + formatted

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=text,
            reply_markup=buttons
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
            scope.get('user'), scope.get('project'), scope.get('start_date'), scope.get('end_date'),
            username=credentials.get('username'), password=credentials.get('password')
        )
        all_worklogs, status_code = self._bot_instance.jira.get_worklogs_by_id(
            issues_ids, username=credentials['username'], password=credentials['password']
        )
        user_logs = self._bot_instance.jira.get_user_worklogs(all_worklogs, scope.get('user'), display_name=True)

        # comparison of the time interval (the time of the log should be between the start and end dates)
        for log in user_logs:
            logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(
                    '{} {}\n{}'.format(issues_ids[log.issueId], log.timeSpent, utils.to_human_date(logged_time))
                )

        start_line = '{user} worklog on {project} from {start_date} to {end_date}\n\n'.format(**scope)
        key = '{username}:{project}:{start_date}:{end_date}'.format(**scope, username=scope.get('user'))
        formatted, buttons = self._bot_instance.save_into_cache(user_worklogs, key)

        if not formatted:
            text = start_line + 'No data about {user} worklogs on {project} from ' \
                                '{start_date} to {end_date}'.format(**scope)
        else:
            text = start_line + formatted

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=text,
            reply_markup=buttons
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
            permission, status = self._bot_instance.jira.is_admin_permissions(
                username=credentials.get('username'), password=credentials.get('password')
            )

            if not permission:
                message = 'You have no permissions to use this function'
                bot.edit_message_text(text=message, chat_id=scope['chat_id'], message_id=scope['message_id'])
                return

        _pattern = 'tproject_u:{start_date}:{end_date}:{project}'.format(**scope) + ':{}'
        obj.handler(bot, scope, credentials, pattern=_pattern, footer='tracking-pu')

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tproject')
