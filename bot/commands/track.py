from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory
from .issue import ChooseProjectMenuCommand

JIRA_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
USER_DATE_FORMAT = '%Y-%m-%d'


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


class ChooseDeveloperCommand(AbstractCommand):

    def handler(self, bot, scope: dict, credentials: dict, *args, **kwargs):
        """Displaying inline keyboard with developers names"""

        buttons = list()
        _callback = kwargs.get('pattern')
        _footer = kwargs.get('footer')

        developers, status = self._bot_instance.jira.get_developers(
            username=credentials.get('username'), password=credentials.get('password')
        )

        if not developers:
            bot.edit_message_text(
                text="Sorry, can't get developers at this moment",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        for fullname in sorted(developers):
            buttons.append(
                InlineKeyboardButton(text=fullname, callback_data=_callback.format(fullname))
            )

        footer_button = [
            InlineKeyboardButton('« Back', callback_data=_footer)
        ]

        buttons = InlineKeyboardMarkup(
            utils.build_menu(buttons, n_cols=2, footer_buttons=footer_button)
        )

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Choose one of the developer',
            reply_markup=buttons
        )


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

    def handler(self, bot, scope: dict, credentials: dict, *args, **kwargs):
        """Shows all worklogs by selected project in selected date interval"""
        start_date = utils.to_datetime(scope['start_date'], scope['user_d_format'])
        end_date = utils.to_datetime(scope['end_date'], scope['user_d_format'])
        project_worklogs = list()

        if start_date > end_date:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='The end date can not be less than the start date',
            )
            return

        issues_ids, status_code = self._bot_instance.jira.get_project_issues(
            project=scope.get('project'), username=credentials.get('username'), password=credentials.get('password')
        )
        all_worklogs, status_code = self._bot_instance.jira.get_issues_worklogs(
            issues_ids, username=credentials['username'], password=credentials['password']
        )

        # comparison of the time interval (the time of the log should be between the start and end dates)
        for i_log in all_worklogs:
            for log in i_log:
                logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

                if (start_date <= logged_time) and (logged_time <= end_date):
                    project_worklogs.append(
                        '{} {} {}\n{}'.format(
                            issues_ids[log.issueId], log.author.displayName, log.timeSpent, log.created
                        )
                    )

        start_line = '{project} work log from {start_date} to {end_date}\n\n'.format(**scope)
        if project_worklogs:
            formatted = '\n\n'.join(project_worklogs)
        else:
            formatted = 'No data about worklogs in this time interval'

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=start_line + formatted,
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
                text='The end date can not be less than the start date',
            )
            return

        issues_ids, status_code = self._bot_instance.jira.get_project_issues(
            scope.get('project'), username=credentials['username'], password=credentials['password']
        )
        all_worklogs, status_code = self._bot_instance.jira.get_issues_worklogs(
            issues_ids, username=credentials['username'], password=credentials['password']
        )
        user_logs = [log for issue in all_worklogs for log in issue if log.author.displayName == scope.get('user')]

        # comparison of the time interval (the time of the log should be between the start and end dates)
        for log in user_logs:
            logged_time = utils.to_datetime(log.created, scope['jira_d_format'])

            if (start_date <= logged_time) and (logged_time <= end_date):
                user_worklogs.append(
                    '{} {}\n{}'.format(issues_ids[log.issueId], log.timeSpent, log.created)
                )

        start_line = '{user} work log on {project} from {start_date} to {end_date}\n\n'.format(**scope)
        if user_worklogs:
            formatted = '\n\n'.join(user_worklogs)
        else:
            formatted = 'No data about {user} work logs on {project} from {start_date} to {end_date}'.format(**scope)

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=start_line + formatted,
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
        'tproject_u_menu': ChooseDeveloperCommand,
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
        if isinstance(obj, ChooseDeveloperCommand):
            if not self._bot_instance.jira.is_admin_permissions(
                username=credentials.get('username'), password=credentials.get('password')
            ):
                message = 'You have no necessary permissions for use this function'
                bot.edit_message_text(text=message, chat_id=scope['chat_id'], message_id=scope['message_id'])
                return

        _pattern = 'tproject_u:{start_date}:{end_date}:{project}'.format(**scope) + ':{}'
        obj.handler(bot, scope, credentials, pattern=_pattern, footer='tracking-pu')

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^tproject')
