from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from common.utils import build_menu, login_required

from .base import AbstractCommand, AbstractCommandFactory


class FilterDispatcherCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        buttons = None
        chat_id = update.message.chat_id
        filter_buttons = list()

        message = "You don't have any favourite filters"
        callback_data = 'filter_p:{}:{}'

        filters = self._bot_instance.jira.get_favourite_filters(auth_data=auth_data)
        if options and filters:
            filter_name = ' '.join(options)

            if filter_name in filters.keys():
                kwargs.update({'filter_name': filter_name, 'filter_id': filters.get(filter_name)})
                return FilterIssuesCommand(self._bot_instance).handler(bot, update, *args, **kwargs)
            else:
                message = 'This filter is not in your favorites'
        elif filters:
            for name in filters.keys():
                filter_buttons.append(
                    InlineKeyboardButton(text=name, callback_data=callback_data.format(name, filters[name]))
                )

            buttons = InlineKeyboardMarkup(
                build_menu(filter_buttons, n_cols=2)
            )

            if buttons:
                message = 'Pick up one of the filters:'
        else:
            message = "You don't have any favourite filters"

        bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=buttons
        )


class FilterDispatcherFactory(AbstractCommandFactory):
    """/filter - returns a list of favorite filters"""

    @login_required
    def command(self, bot, update, *args, **kwargs):
        FilterDispatcherCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('filter', self.command, pass_args=True)


class FilterIssuesCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        new_message = True

        try:
            scope = self._bot_instance.get_query_scope(update)
        except AttributeError:
            telegram_id = update.message.chat_id
            filter_name = kwargs.get('filter_name')
            filter_id = kwargs.get('filter_id')
        else:
            telegram_id = scope['telegram_id']
            new_message = False
            filter_name, filter_id = scope['data'].replace('filter_p:', '').split(':')

        filter_key = 'filter_p:{}:{}'.format(telegram_id, filter_id)

        # shot title
        if new_message:
            bot.send_message(
                text='All tasks which filtered by <b>«{}»</b>:'.format(filter_name),
                chat_id=telegram_id,
                parse_mode=ParseMode.HTML
            )
        else:
            bot.edit_message_text(
                chat_id=telegram_id,
                message_id=scope['message_id'],
                text='All tasks which filtered by <b>«{}»</b>:'.format(filter_name),
                parse_mode=ParseMode.HTML
            )

        issues = self._bot_instance.jira.get_filter_issues(
            filter_id=filter_id, filter_name=filter_name, auth_data=auth_data
        )
        formatted_issues, buttons = self._bot_instance.save_into_cache(data=issues, key=filter_key)

        # shows list of issues
        bot.send_message(
            text=formatted_issues,
            chat_id=telegram_id,
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )


class FilterIssuesFactory(AbstractCommandFactory):
    """/filter -> some filter - return issues getting by a selected filter"""

    @login_required
    def command(self, bot, update, *args, **kwargs):
        FilterIssuesCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^filter_p:')
