import os
from itertools import zip_longest

import pendulum
from pendulum.parsing.exceptions import ParserError
from telegram.ext import CommandHandler

from bot.exceptions import ContextValidationError
from bot.helpers import login_required
from lib import utils

from .base import AbstractCommand


class TimeTrackingDispatcher(AbstractCommand):
    """
    /time <target> <name> [start_date] [end_date] - Shows spended time for users, issues and projects
    """
    command_name = "/time"
    targets = ('user', 'issue', 'project')
    description = utils.read_file(os.path.join('bot', 'templates', 'time_description.tpl'))

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        options = kwargs.get('args')
        parameters_names = ('target', 'name', 'start_date', 'end_date')
        current_date = pendulum.now()
        params = dict(zip_longest(parameters_names, options))
        if params['target'] not in self.targets or not params['name']:
                return self.app.send(bot, update, text=self.description)

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
                return self.app.send(bot, update, text='Invalid date format')
            else:
                params['end_date'] = current_date._end_of_day()
        elif params['start_date'] and params['end_date']:
            try:
                params['start_date'] = pendulum.parse(params['start_date'])
                params['end_date'] = pendulum.parse(params['end_date'])
            except ParserError:
                return self.app.send(bot, update, text='Invalid date format')

        kwargs.update(params)
        if params['target'] == 'issue':
            kwargs.update({'issue': params['name']})
            return IssueTimeTrackerCommand(self.app).handler(bot, update, *args, **kwargs)
        elif params['target'] == 'user':
            kwargs.update({'username': params['name']})
            return UserTimeTrackerCommand(self.app).handler(bot, update, *args, **kwargs)
        elif params['target'] == 'project':
            kwargs.update({'project': params['name']})
            return ProjectTimeTrackerCommand(self.app).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('time', self.handler, pass_args=True)

    @classmethod
    def check_command(cls, command_name):
        # validate command name
        return command_name == cls.command_name

    @classmethod
    def validate_context(cls, context):
        if len(context) < 1:
            raise ContextValidationError(cls.description)

        target = context.pop(0)
        # validate command options
        if target == 'issue':
            if len(context) < 1:
                raise ContextValidationError("<i>ISSUE KEY</i> is a required argument.")
        elif target == 'user':
            if len(context) < 1:
                raise ContextValidationError("<i>USERNAME</i> is a required argument.")
        elif target == 'project':
            if len(context) < 1:
                raise ContextValidationError("<i>KEY</i> is a required argument.")
        else:
            raise ContextValidationError(f"Argument {target} not allowed.")


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
        self.app.jira.is_issue_exists(host=auth_data.jira_host, issue=issue, auth_data=auth_data)
        issue_worklog = self.app.jira.get_issue_worklogs(issue, start_date, end_date, auth_data=auth_data)

        seconds = sum(worklog.get('time_spent_seconds', 0) for worklog in issue_worklog)
        spended_time = utils.calculate_tracking_time(seconds)

        template = f'Time, spended on issue <b>{issue}</b> from <b>{start_date.to_date_string()}</b> ' \
                   f'to <b>{end_date.to_date_string()}</b>: '
        text = template + str(spended_time) + ' h'
        return self.app.send(bot, update, text=text)


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
        self.app.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)
        utils.validate_date_range(start_date, end_date)

        all_worklogs = self.app.jira.get_all_user_worklogs(
            username, start_date, end_date, auth_data=auth_data
        )
        all_user_logs = self.app.jira.define_user_worklogs(
            all_worklogs, username, name_key='author_name'
        )
        seconds = sum(worklog.get('time_spent_seconds', 0) for worklog in all_user_logs)
        spended_time = utils.calculate_tracking_time(seconds)

        template = f'User <b>{username}</b> from <b>{start_date.to_date_string()}</b> ' \
                   f'to <b>{end_date.to_date_string()}</b> spent: '
        text = template + str(spended_time) + ' h'
        return self.app.send(bot, update, text=text)


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
        self.app.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)
        utils.validate_date_range(start_date, end_date)

        all_worklogs = self.app.jira.get_project_worklogs(
            project, start_date, end_date, auth_data=auth_data
        )

        seconds = sum(worklog.get('time_spent_seconds', 0) for worklog in all_worklogs)
        spended_time = utils.calculate_tracking_time(seconds)

        template = f'Spended time on project <b>{project}</b> ' \
                   f'from <b>{start_date.to_date_string()}</b> to <b>{end_date.to_date_string()}</b>: '
        text = template + str(spended_time) + ' h'
        return self.app.send(bot, update, text=text)
