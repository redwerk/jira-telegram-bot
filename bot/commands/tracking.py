import os
import re

import dateparser
import pendulum
from pendulum.parsing.exceptions import ParserError
from telegram.ext import CommandHandler

from bot.exceptions import (ContextValidationError, DateTimeValidationError,
                            JiraEmptyData)
from bot.helpers import login_required, with_progress
from bot.schedules import schedule_commands
from lib import utils

from .base import AbstractCommand

US_TIMEZONES = [
    "US/Alaska",
    "US/Aleutian",
    "US/Arizona",
    "US/Central",
    "US/East-Indiana",
    "US/Eastern",
    "US/Hawaii",
    "US/Indiana-Starke",
    "US/Michigan",
    "US/Mountain",
    "US/Pacific",
    "US/Pacific-New",
    "US/Samoa",
]


class TimeTrackingDispatcher(AbstractCommand):
    """
    /time <target> <name> [start_date] [end_date] - Shows spent time for users, issues and projects
    """
    targets = ('user', 'issue', 'project')
    available_days = ('today', 'yesterday')
    description = utils.read_file(os.path.join('bot', 'templates', 'time_description.tpl'))

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        current_date = pendulum.now()
        params = dict()
        options = kwargs.get('args')
        if len(options) < 3:
                return self.app.send(bot, update, text=self.description)

        params['target'] = options.pop(0)
        params['name'] = options.pop(0)
        if params.get('target') not in self.targets or not options:
            return self.app.send(bot, update, text=self.description)

        if len(options) == 1 and options[0] in self.available_days:
            if options[0] == 'today':
                date = self.__get_normalize_date(
                    current_date.to_date_string(), self.app.jira.get_jira_tz(**kwargs)
                )
                params['start_date'] = pendulum.create(
                    date.year, date.month, date.day)._start_of_day()
                params['end_date'] = pendulum.create(
                    date.year, date.month, date.day)._end_of_day()
            elif options[0] == 'yesterday':
                date = self.__get_normalize_date(
                    current_date.subtract(days=1).to_date_string(),
                    self.app.jira.get_jira_tz(**kwargs)
                )
                params['start_date'] = pendulum.create(
                    date.year, date.month, date.day)._start_of_day()
                params['end_date'] = pendulum.create(
                    date.year, date.month, date.day)._end_of_day()
        elif len(options) == 1:
            # if the start date is specified - the command will be executed
            # inclusively from the start date to today's date
            try:
                start_date = self.__get_normalize_date(
                    options[0], self.app.jira.get_jira_tz(**kwargs)
                )
                params['start_date'] = pendulum.create(
                    start_date.year, start_date.month, start_date.day)._start_of_day()
            except ParserError:
                return self.app.send(bot, update, text='Invalid date format')
            else:
                end_date = self.__get_normalize_date(
                    current_date.to_date_string(), self.app.jira.get_jira_tz(**kwargs)
                )
                params['end_date'] = pendulum.create(
                    end_date.year, end_date.month, end_date.day)._end_of_day()
        elif len(options) > 1:
            try:
                start_date = self.__get_normalize_date(
                    options[0], self.app.jira.get_jira_tz(**kwargs)
                )
                end_date = self.__get_normalize_date(
                    options[1], self.app.jira.get_jira_tz(**kwargs)
                )
                params['start_date'] = pendulum.create(
                    start_date.year, start_date.month, start_date.day)._start_of_day()
                params['end_date'] = pendulum.create(
                    end_date.year, end_date.month, end_date.day)._end_of_day()
            except ParserError:
                return self.app.send(bot, update, text='Invalid date format')
        else:
            return self.app.send(bot, update, text=self.description)

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
    def validate_context(cls, context):
        if len(context) < 3:  # target, name, start_date are required
            raise ContextValidationError(cls.description)

        target = context.pop(0)
        # validate command options
        if target == 'issue':
            if len(context) < 2:
                raise ContextValidationError("<i>ISSUE KEY</i> and <i>START DATE</i> are required arguments.")
        elif target == 'user':
            if len(context) < 2:
                raise ContextValidationError("<i>USERNAME</i> and <i>START DATE</i> are required arguments.")
        elif target == 'project':
            if len(context) < 2:
                raise ContextValidationError("<i>KEY</i> and <i>START DATE</i> are required arguments.")
        else:
            raise ContextValidationError(f"Argument {target} not allowed.")

    def __identify_of_date_format(self, date, timezone):
        """
        The function determines and returns the date format
        based on the date and timezone

        :param date: date for parsing
        :param timezone: timezone for defining the format
        :return: date format for configuring library 'date_formats' dateparser
        """
        from enum import Enum

        class NoValue(Enum):
            def __repr__(self):
                return '<%s.%s>' % (self.__class__.__name__, self.name)

        class DateFormatPatterns(NoValue):
            LITTLEENDIAN = r"\d{2}(.*?)\d{2}(.*?)\d{4}",
            MIDDLEENDIAN_0 = r"\w{3,}(.*?)\d{2}(.*?)\d{4}",
            MIDDLEENDIAN_1 = r"\d{2}(.*?)\w{3,}(.*?)\d{4}",
            BIGENDIAN_0 = r"\d{4}(.*?)\d{2}(.*?)\d{2}",
            BIGENDIAN_1 = r"\d{4}(.*?)\w{3,}(.*?)\d{2}",

        delimiters = "/.-"
        delimiter = str()
        for item in delimiters:
            if item in date:
                if delimiter and item != delimiter:
                    raise DateTimeValidationError(f"Too many delimiters in date.")
                else:
                    delimiter = item

        date_matches = {
            DateFormatPatterns.LITTLEENDIAN: "%m{dlm}%d{dlm}%Y".format(dlm=delimiter)
            if timezone in US_TIMEZONES else "%d{dlm}%m{dlm}%Y".format(dlm=delimiter),
            DateFormatPatterns.MIDDLEENDIAN_0: "%B{dlm}%d{dlm}%Y".format(dlm=delimiter),
            DateFormatPatterns.MIDDLEENDIAN_1: "%d{dlm}%B{dlm}%Y".format(dlm=delimiter),
            DateFormatPatterns.BIGENDIAN_0: "%Y{dlm}%m{dlm}%d".format(dlm=delimiter),
            DateFormatPatterns.BIGENDIAN_1: "%Y{dlm}%B{dlm}%d".format(dlm=delimiter),
        }

        for date_pattern in DateFormatPatterns:
            if re.match(re.compile(date_pattern.value[0]), date):
                return date_matches.get(date_pattern)

    def __get_normalize_date(self, date, timezone):
        try:
            date_fmt = self.__identify_of_date_format(date, timezone)
            return dateparser.parse(date, date_formats=[date_fmt], languages=['en', 'ru'])
        except TypeError:
            raise TypeError(f"Invalid format date.")


class IssueTimeTrackerCommand(AbstractCommand):
    """Shows spent time at the issue"""
    @with_progress()
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        issue = kwargs.get('issue')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        utils.validate_date_range(start_date, end_date)
        try:
            self.app.jira.is_issue_exists(host=auth_data.jira_host, issue=issue, auth_data=auth_data)
            spent_time = self.app.jira.get_issue_worklogs(issue, start_date, end_date, auth_data=auth_data)
        except JiraEmptyData as err:
            return self.app.send(bot, update, text=err.message, **kwargs)

        is_united_states_timezone = self.app.jira.get_jira_tz(**kwargs) in US_TIMEZONES
        date_fmt = "%m-%d-%Y" if is_united_states_timezone else "%Y-%m-%d"
        template = f'Time spent on issue <b>{issue}</b> from <b>{start_date.strftime(date_fmt)}</b> ' \
                   f'to <b>{end_date.strftime(date_fmt)}</b>: '
        text = template + str(round(spent_time, 2)) + ' h'
        return self.app.send(bot, update, text=text, **kwargs)


class UserTimeTrackerCommand(AbstractCommand):
    """Shows spent time of the user"""
    @with_progress()
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        username = kwargs.get('username')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')

        # check if the user exists on Jira host
        self.app.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)
        utils.validate_date_range(start_date, end_date)
        try:
            all_worklogs = self.app.jira.get_all_user_worklogs(
                username, start_date, end_date, auth_data=auth_data
            )
            all_user_logs = self.app.jira.define_user_worklogs(
                all_worklogs, username, name_key='author_name'
            )
        except JiraEmptyData as err:
            return self.app.send(bot, update, text=err.message, **kwargs)

        seconds = sum(worklog.get('time_spent_seconds', 0) for worklog in all_user_logs)
        spent_time = utils.calculate_tracking_time(seconds)

        is_united_states_timezone = self.app.jira.get_jira_tz(**kwargs) in US_TIMEZONES
        date_fmt = "%m-%d-%Y" if is_united_states_timezone else "%Y-%m-%d"
        template = f'User <b>{username}</b> from <b>{start_date.strftime(date_fmt)}</b> ' \
                   f'to <b>{end_date.strftime(date_fmt)}</b> spent: '
        text = template + str(round(spent_time, 2)) + ' h'
        return self.app.send(bot, update, text=text, **kwargs)


class ProjectTimeTrackerCommand(AbstractCommand):
    """Shows spent time at the project"""
    @with_progress()
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        project = kwargs.get('project')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        # check if the project exists on Jira host
        self.app.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)
        utils.validate_date_range(start_date, end_date)
        try:
            spent_time = self.app.jira.get_project_worklogs(project, start_date, end_date, auth_data=auth_data)
        except JiraEmptyData as err:
            return self.app.send(bot, update, text=err.message, **kwargs)

        is_united_states_timezone = self.app.jira.get_jira_tz(**kwargs) in US_TIMEZONES
        date_fmt = "%m-%d-%Y" if is_united_states_timezone else "%Y-%m-%d"
        template = (
            f'Time spent on project <b>{project}</b> '
            f'from <b>{start_date.strftime(date_fmt)}</b> to <b>{end_date.strftime(date_fmt)}</b>: '
        )
        text = template + str(round(spent_time, 2)) + ' h'
        return self.app.send(bot, update, text=text, **kwargs)


schedule_commands.register("time", TimeTrackingDispatcher)
