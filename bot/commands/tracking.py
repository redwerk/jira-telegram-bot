from itertools import zip_longest

import pendulum
from pendulum.parsing.exceptions import ParserError
from telegram.ext import CommandHandler

from common import utils

from .base import AbstractCommand, SendMessageFactory


class TimeTrackingDispatcher(AbstractCommand):
    """
    /time <target> <name> [start_date] [end_date] - Shows spended time for users, issues and projects
    """
    targets = ('user', 'issue', 'project')

    @utils.login_required
    def handler(self, bot, update, *args, **kwargs):
        options = kwargs.get('args')
        parameters_names = ('target', 'name', 'start_date', 'end_date')
        current_date = pendulum.now()
        description = "<b>Command description:</b>\n" \
                      "/time issue <i>issue-key</i> - returns a report of spend time of issue\n" \
                      "/time user <i>username</i> - returns a report of spend time of user\n" \
                      "/time project <i>KEY</i> - returns a report of spend time of project\n\n" \
                      "<i>If the date range is not specified, the command is executed for today</i>\n" \
                      "<i>If the start date is specified - the command will be executed inclusively from the " \
                      "start date to today's date</i>"

        params = dict(zip_longest(parameters_names, options))
        if params['target'] not in self.targets or not params['name']:
                return SendMessageFactory.send(bot, update, text=description, simple_message=True)

        if not params['start_date'] and not params['end_date']:
            # if has not date range - command execute for today
            params['start_date'] = current_date._start_of_day()
            params['end_date'] = current_date._end_of_day()
        elif params['start_date'] and not params['end_date']:
            # if the start date is specified - the command will be executed
            # inclusively from the start date to today's date
            try:
                params['start_date'] = pendulum.parse(params['start_date'])
            except ParserError:
                return SendMessageFactory.send(bot, update, text='Invalid date format', simple_message=True)
            else:
                params['end_date'] = current_date._end_of_day()
        elif params['start_date'] and params['end_date']:
            try:
                params['start_date'] = pendulum.parse(params['start_date'])
                params['end_date'] = pendulum.parse(params['end_date'])
            except ParserError:
                return SendMessageFactory.send(bot, update, text='Invalid date format', simple_message=True)

        kwargs.update(params)
        if params['target'] == 'issue':
            kwargs.update({'issue': params['name']})
            return IssueTimeTrackerCommand(self._bot_instance).handler(bot, update, *args, **kwargs)
        elif params['target'] == 'user':
            kwargs.update({'username': params['name']})
            return UserTimeTrackerCommand(self._bot_instance).handler(bot, update, *args, **kwargs)
        elif params['target'] == 'project':
            kwargs.update({'project': params['name']})
            return ProjectTimeTrackerCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('time', self.handler, pass_args=True)


class IssueTimeTrackerCommand(AbstractCommand):
    """
    Shows spended time at the issue
    """
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        issue = kwargs.get('issue')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')

        utils.validate_date_range(start_date, end_date)
        self._bot_instance.jira.is_issue_exists(host=auth_data.jira_host, issue=issue, auth_data=auth_data)
        issue_worklog = self._bot_instance.jira.get_issue_worklogs(issue, start_date, end_date, auth_data=auth_data)

        seconds = 0
        for log in sorted(issue_worklog, key=lambda x: x.get('created')):
            seconds += log.get('time_spent_seconds')

        if seconds:
            spended_time = utils.calculate_tracking_time(seconds)
        else:
            spended_time = 0

        template = f'Time, spended on issue <b>{issue}</b> from from <b>{start_date.to_date_string()}</b> ' \
                   f'to <b>{end_date.to_date_string()}</b>: '
        text = template + str(spended_time) + ' h'
        return SendMessageFactory.send(bot, update, text=text, simple_message=True)


class UserTimeTrackerCommand(AbstractCommand):
    """
    Shows spended time of the user
    """

    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        username = kwargs.get('username')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')

        # check if the user exists on Jira host
        self._bot_instance.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)
        utils.validate_date_range(start_date, end_date)

        all_worklogs = self._bot_instance.jira.get_all_user_worklogs(
            username, start_date, end_date, auth_data=auth_data
        )
        all_user_logs = self._bot_instance.jira.define_user_worklogs(
            all_worklogs, username, name_key='author_name'
        )
        seconds = 0
        for log in sorted(all_user_logs, key=lambda x: x.get('created')):
            seconds += log.get('time_spent_seconds')

        if seconds:
            spended_time = utils.calculate_tracking_time(seconds)
        else:
            spended_time = 0

        template = f'User <b>{username}</b> from from <b>{start_date.to_date_string()}</b> ' \
                   f'to <b>{end_date.to_date_string()}</b> spent: '
        text = template + str(spended_time) + ' h'
        return SendMessageFactory.send(bot, update, text=text, simple_message=True)


class ProjectTimeTrackerCommand(AbstractCommand):
    """
    Shows spended time at the project
    """

    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        project = kwargs.get('project')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')

        # check if the project exists on Jira host
        self._bot_instance.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)
        utils.validate_date_range(start_date, end_date)

        all_worklogs = self._bot_instance.jira.get_project_worklogs(
            project, start_date, end_date, auth_data=auth_data
        )
        seconds = 0
        for log in sorted(all_worklogs, key=lambda x: x.get('created')):
            seconds += log.get('time_spent_seconds')

        if seconds:
            spended_time = utils.calculate_tracking_time(seconds)
        else:
            spended_time = 0
        template = f'Spended time on project <b>{project}</b> ' \
                   f'from <b>{start_date.to_date_string()}</b> to <b>{end_date.to_date_string()}</b>: '
        text = template + str(spended_time) + ' h'
        return SendMessageFactory.send(bot, update, text=text, simple_message=True)
