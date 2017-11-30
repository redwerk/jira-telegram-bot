from itertools import zip_longest

import pendulum
from pendulum.parsing.exceptions import ParserError
from telegram.ext import CommandHandler

from common import utils

from .base import AbstractCommand, SendMessageFactory


class TimeTrackingDispatcher(AbstractCommand):
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
            start_date = current_date._start_of_day()
            end_date = current_date._end_of_day()
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
            kwargs.update({'issue': params['target']})
            return IssueTimeTrackerCommand(self._bot_instance).handler(bot, update, *args, **kwargs)
        elif params['target'] == 'user':
            kwargs.update({'username': params['target']})
            return UserTimeTrackerCommand(self._bot_instance).handler(bot, update, *args, **kwargs)
        elif params['target'] == 'project':
            kwargs.update({'project': params['target']})
            return ProjectTimeTrackerCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('time', self.handler, pass_args=True)


class IssueTimeTrackerCommand(AbstractCommand):
    def handler(self, bot, update, *args, **kwargs):
        return SendMessageFactory.send(bot, update, text='Hello from IssueTimeTrackerCommand', simple_message=True)


class UserTimeTrackerCommand(AbstractCommand):
    def handler(self, bot, update, *args, **kwargs):
        return SendMessageFactory.send(bot, update, text='Hello from UserTimeTrackerCommand', simple_message=True)


class ProjectTimeTrackerCommand(AbstractCommand):
    def handler(self, bot, update, *args, **kwargs):
        return SendMessageFactory.send(bot, update, text='Hello from ProjectTimeTrackerCommand', simple_message=True)
