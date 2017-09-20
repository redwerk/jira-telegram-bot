from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot.utils import build_menu, is_user_exists, login_required

from .base import AbstractCommand, AbstractCommandFactory
from .issue import UserUnresolvedIssuesCommand


class FilterListCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        chat_id = update.message.chat_id
        filter_buttons = list()

        message = "You don't have any favourite filters"
        callback_data = 'filter:{}:{}'

        filters, error = self._bot_instance.jira.get_favourite_filters(auth_data=auth_data)
        for name in filters.keys():
            filter_buttons.append(
                InlineKeyboardButton(text=name, callback_data=callback_data.format(name, filters[name]))
            )

        buttons = InlineKeyboardMarkup(
            build_menu(filter_buttons, n_cols=2)
        )

        if buttons:
            message = 'Pick up one of the filters:'

        bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=buttons
        )


class FilterListFactory(AbstractCommandFactory):
    """/filter - returns a list of favorite filters"""

    @login_required
    @is_user_exists
    def command(self, bot, update, *args, **kwargs):
        chat_id = update.message.chat_id
        auth_data, message = self._bot_instance.get_and_check_cred(chat_id)
        FilterListCommand(self._bot_instance).handler(bot, update, auth_data=auth_data, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('filter', self.command)


class FilterIssuesCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        scope = self._bot_instance.get_query_scope(update)
        filter_name, filter_id = scope['data'].replace('filter:', '').split(':')
        filter_key = 'filter:{}:{}'.format(scope['telegram_id'], filter_id)

        issues, error = self._bot_instance.jira.get_filter_issues(filter_id=filter_id, auth_data=auth_data)
        UserUnresolvedIssuesCommand.show_title(
            bot,
            'All tasks which filtered by <b>«{}»</b>:'.format(filter_name),
            scope['chat_id'],
            scope['message_id']
        )

        if not issues:
            message = 'No tasks which filtered by <b>«{}»</b>'.format(filter_name)
            UserUnresolvedIssuesCommand.show_content(bot, message, scope['chat_id'])
            return

        formatted_issues, buttons = self._bot_instance.save_into_cache(data=issues, key=filter_key)
        UserUnresolvedIssuesCommand.show_content(bot, formatted_issues, scope['chat_id'], buttons)


class FilterIssuesFactory(AbstractCommandFactory):
    """/filter -> some filter - return issues getting by a selected filter"""

    def command(self, bot, update, *args, **kwargs):
        chat_id = update.callback_query.from_user.id
        auth_data, message = self._bot_instance.get_and_check_cred(chat_id)
        FilterIssuesCommand(self._bot_instance).handler(bot, update, auth_data=auth_data, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^filter')
