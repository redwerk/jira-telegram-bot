import datetime

from telegram.ext import CommandHandler

from common.utils import login_required

from .base import AbstractCommand, SendMessageFactory
from .issue import ListUnresolvedIssuesCommand
from ..schedules import ScheduleTask


class ScheduleCommand(AbstractCommand):
    """/schedule <command> - create schedule command"""

    @login_required
    def handler(self, bot, update, args, **kwargs):
        interval = datetime.timedelta(seconds=60)
        ScheduleTask.create(update, ListUnresolvedIssuesCommand, ['my'], interval)
        SendMessageFactory.send(
            bot,
            update,
            text="command was created saccessfully!",
            simple_message=True
        )

    def command_callback(self):
        return CommandHandler('schedule', self.handler, pass_args=True)
