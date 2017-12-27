from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot.helpers import login_required, get_query_scope
from bot.exceptions import ContextValidationError
from bot.inlinemenu import build_menu
from bot.schedules import schedule_commands

from .base import AbstractCommand


class FilterDispatcherCommand(AbstractCommand):
    """/filter - returns a list of favorite filters"""

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        callback_data = 'filter_p:{}:{}'
        filter_buttons = list()

        filters = self.app.jira.get_favourite_filters(auth_data=auth_data)
        if options and filters:
            filter_name = ' '.join(options)

            if filter_name in filters.keys():
                kwargs.update({'filter_name': filter_name, 'filter_id': filters.get(filter_name)})
                return FilterIssuesCommand(self.app).handler(bot, update, *args, **kwargs)
            else:
                text = 'This filter is not in your favorites'
                return self.app.send(bot, update, text=text)
        elif filters:
            for name in filters.keys():
                filter_buttons.append(
                    InlineKeyboardButton(text=name, callback_data=callback_data.format(name, filters[name]))
                )

            buttons = InlineKeyboardMarkup(build_menu(filter_buttons, n_cols=2))
            if buttons:
                text = 'Pick up one of the filters:'
                return self.app.send(bot, update, text=text, buttons=buttons)

        self.app.send(bot, update, text="You don't have any favourite filters")

    def command_callback(self):
        return CommandHandler('filter', self.handler, pass_args=True)


class FilterIssuesCommand(AbstractCommand):
    """/filter -> some filter - return issues getting by a selected filter"""
    command_name = "/filter"

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')

        try:
            scope = get_query_scope(update)
        except AttributeError:
            telegram_id = update.message.chat_id
            filter_name = kwargs.get('filter_name')
            filter_id = kwargs.get('filter_id')
        else:
            telegram_id = scope['telegram_id']
            filter_name, filter_id = scope['data'].replace('filter_p:', '').split(':')

        title = 'All tasks which filtered by «{}»:'.format(filter_name)
        raw_items = self.app.jira.get_filter_issues(
            filter_id=filter_id, filter_name=filter_name, auth_data=auth_data
        )
        key = 'filter_p:{}:{}'.format(telegram_id, filter_id)
        self.app.send(bot, update, title=title, raw_items=raw_items, key=key)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^filter_p:')

    @classmethod
    def check_command(cls, command_name):
        # validate command name
        return command_name == cls.command_name

    @classmethod
    def validate_context(cls, context):
        if len(context) < 1:
            raise ContextValidationError("<i>Filter Name</i> is a required argument.")


schedule_commands.register(FilterIssuesCommand)
