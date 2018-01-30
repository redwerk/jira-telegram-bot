import re
import os
from functools import lru_cache

from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import login_required
from bot.schedules import ScheduleTask
from bot.exceptions import ScheduleValidationError, ContextValidationError
from bot.inlinemenu import build_menu
from bot.parsers import cron_parser, command_parser, command_re
from lib.utils import read_file

from .base import AbstractCommand


class ScheduleCommand(AbstractCommand):
    """"/schedule <command> <periodicity> - create new schedule command"""

    @staticmethod
    @lru_cache(1)
    def get_description():
        filename = os.path.join("bot", "templates", "schedule_description.tpl")
        return read_file(filename)

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        ScheduleCommand.validate_context(kwargs["args"])

        cmd_name = " ".join(kwargs["args"])
        if not cmd_name.startswith("/"):
            cmd_name = "/" + cmd_name

        # get user timezone from JIRA
        tz = self.app.jira.get_jira_tz(**kwargs)
        # parse command and options
        m = re.match(command_re, cmd_name)
        if not m:
            raise ScheduleValidationError("Entered value is not correct")

        data = m.groupdict(None)
        command, context = command_parser(data.get("callback"))
        interval = cron_parser(data.get("type"), data.get("opt") or "")
        # create schedule command
        ScheduleTask.create(update, cmd_name, tz, interval, command, context)
        self.app.send(bot, update, text="Schedule command was created successfully!")

    def command_callback(self):
        return CommandHandler('schedule', self.handler, pass_args=True)

    @classmethod
    def validate_context(cls, context):
        if len(context) < 1:
            raise ContextValidationError(cls.get_description())


class ScheduleCommandList(AbstractCommand):
    """/unschedule - get schedule commands list"""

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        entries = self.app.db.get_schedule_commands(user_id)
        buttons = list()
        if entries.count():
            text = 'Click to remove schedule commands:'
            for entry in entries:
                data = f'unschedule:{entry["_id"]}'
                button = InlineKeyboardButton(entry.get("name"), callback_data=data)
                buttons.append(button)
            reply_markup = InlineKeyboardMarkup(build_menu(buttons))
        else:
            text = "You don't have schedule commands"
            reply_markup = None

        self.app.send(bot, update, text=text, buttons=reply_markup)

    def command_callback(self):
        return CommandHandler('unschedule', self.handler)


class ScheduleCommandDelete(AbstractCommand):
    """Delete schedule command by id"""

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        callback_data = update.callback_query.data
        entry_id = callback_data.split(":")[-1]
        if self.app.db.remove_schedule_command(entry_id):
            ScheduleCommandList(self.app).handler(bot, update, *args, **kwargs)
        else:
            self.app.send(bot, update, text="This command can't be deleted.")

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^unschedule:')
