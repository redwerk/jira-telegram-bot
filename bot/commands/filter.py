from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from common.utils import build_menu, login_required

from .base import AbstractCommand, SendMessageFactory


class FilterDispatcherCommand(AbstractCommand):
    """/filter - returns a list of favorite filters"""

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        callback_data = 'filter_p:{}:{}'
        filter_buttons = list()

        filters = self._bot_instance.jira.get_favourite_filters(auth_data=auth_data)
        if options and filters:
            filter_name = ' '.join(options)

            if filter_name in filters.keys():
                kwargs.update({'filter_name': filter_name, 'filter_id': filters.get(filter_name)})
                return FilterIssuesCommand(self._bot_instance).handler(bot, update, *args, **kwargs)
            else:
                text = 'This filter is not in your favorites'
                return SendMessageFactory.send(bot, update, text=text, simple_message=True)
        elif filters:
            for name in filters.keys():
                filter_buttons.append(
                    InlineKeyboardButton(text=name, callback_data=callback_data.format(name, filters[name]))
                )

            buttons = InlineKeyboardMarkup(
                build_menu(filter_buttons, n_cols=2)
            )

            if buttons:
                text = 'Pick up one of the filters:'
                return SendMessageFactory.send(bot, update, text=text, buttons=buttons, simple_message=True)

        SendMessageFactory.send(bot, update, text="You don't have any favourite filters", simple_message=True)

    def command_callback(self):
        return CommandHandler('filter', self.handler, pass_args=True)


class FilterIssuesCommand(AbstractCommand):
    """/filter -> some filter - return issues getting by a selected filter"""

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')

        try:
            scope = self._bot_instance.get_query_scope(update)
        except AttributeError:
            telegram_id = update.message.chat_id
            filter_name = kwargs.get('filter_name')
            filter_id = kwargs.get('filter_id')
        else:
            telegram_id = scope['telegram_id']
            filter_name, filter_id = scope['data'].replace('filter_p:', '').split(':')

        title = 'All tasks which filtered by «{}»:'.format(filter_name)
        raw_items = self._bot_instance.jira.get_filter_issues(
            filter_id=filter_id, filter_name=filter_name, auth_data=auth_data
        )
        key = 'filter_p:{}:{}'.format(telegram_id, filter_id)
        SendMessageFactory.send(bot, update, title=title, raw_items=raw_items, key=key)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^filter_p:')
