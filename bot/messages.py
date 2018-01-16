import logging
from abc import ABCMeta, abstractmethod

from telegram import ParseMode

from lib.db import MongoBackend
from .exceptions import SendMessageHandlerError
from .paginations import split_by_pages, get_pagination_keyboard

logger = logging.getLogger('bot')


class BaseMessage(metaclass=ABCMeta):
    """Base bot message class.

    Args:
        bot (telegram.Bot): telegram bot instance
        update (telegram.Update): Update instance
    Keyword arguments:
        title (str): Title of the message (the text is bold)
        text (str): Simple text in message (withour editing)
        buttons: any buttons to show in chat
        items (list): list of strings with any data
        key (str): key for cached data
        page (int): number of page that user clicked (at inline keyboard)
        page_count (int): total count of the pages (for generating a new inline keyboard)
        raw_items (dict): raw JIRA issue objects, need to format before display
    """
    db = MongoBackend()
    issues_per_page = 10
    callback_paginator_key = 'paginator:{}'

    def __init__(self, bot, update, **kwargs):
        self.bot = bot
        self.update = update
        self.message_id = kwargs.get('message_id')
        self.title = kwargs.get('title')
        self.text = kwargs.get('text')
        self.buttons = kwargs.get('buttons')
        self.items = kwargs.get('items')
        self.key = kwargs.get('key')
        self.page = kwargs.get('page')
        self.page_count = kwargs.get('page_count')
        self.raw_items = kwargs.get('raw_items')

    @abstractmethod
    def send(self):
        """Send message to chat. This method must be implemented
        in your class.
        """
        pass


class ChatMessage(BaseMessage):

    def send(self):
        chat_id = self.get_metadata()
        send = self.bot.edit_message_text if self.message_id else self.bot.send_message
        if self.items or self.raw_items:
            # formatting list of strings from JIRA issue objects
            if self.raw_items:
                self.items = self.issues_format()

            if len(self.items) > self.issues_per_page:
                # if items count more than one page
                text, buttons = self.processing_multiple_pages()
            else:
                text, buttons = self.processing_single_page()

            context = dict(
                chat_id=chat_id,
                message_id=self.message_id,
                text=text,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            context = dict(
                chat_id=chat_id,
                message_id=self.message_id,
                text=self.text,
                reply_markup=self.buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

        return send(**context)

    def issues_format(self):
        """
        Formats issues into string by template: issue id, title and permalink
        """
        issues_list = list()
        try:
            for issue in self.raw_items:
                issues_str = '<a href="{permalink}">{key}</a> {summary}'.format(
                    key=issue.key, summary=issue.fields.summary, permalink=issue.permalink()
                )
                issues_list.append(issues_str)
        except AttributeError as e:
            logger.exception(e)

        return issues_list

    def message_format(self, items):
        f_title = '<b>{}</b>\n\n'.format(self.title)
        f_issues = '\n\n'.join(items)
        return f_title + f_issues

    def get_metadata(self):
        return self.update.message.chat_id

    def save_into_cache(self, splitted_data):
        page_count = len(splitted_data)
        status = self.db.create_cache(self.key, self.title, splitted_data, page_count)
        if not status:
            raise SendMessageHandlerError('An attempt to write content to the cache failed: {}'.format(self.key))

    def processing_multiple_pages(self):
        # if there are many values (the first query) - cache and
        # give the first page of results with inline keyboard
        callback_key = self.callback_paginator_key.format(self.key)
        splitted_data = split_by_pages(self.items, self.issues_per_page)
        self.save_into_cache(splitted_data)

        text = self.message_format(splitted_data[0])  # return first page
        buttons = get_pagination_keyboard(
            current=1,
            max_page=len(splitted_data),
            str_key=callback_key + '#{}'
        )

        return text, buttons

    def processing_single_page(self):
        # in general, displaying a selected page from cache with inline keyboard
        buttons = None
        callback_key = self.callback_paginator_key.format(self.key)
        text = self.message_format(self.items)

        if self.page and self.page_count:
            buttons = get_pagination_keyboard(
                current=self.page,
                max_page=self.page_count,
                str_key=callback_key + '#{}'
            )

        return text, buttons


class AfterActionMessage(ChatMessage):

    def send(self):
        chat_id, message_id = self.get_metadata()

        if self.items or self.raw_items:
            # formatting list of strings from JIRA issue objects
            if self.raw_items:
                self.items = self.issues_format()

            if len(self.items) > self.issues_per_page:
                # if items count more than one page
                text, buttons = self.processing_multiple_pages()
            else:
                text, buttons = self.processing_single_page()

            result = self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            result = self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self.text,
                reply_markup=self.buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

        return result

    def get_metadata(self):
        query = self.update.callback_query
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return chat_id, message_id


class InlineMessage(BaseMessage):

    def send(self):
        # TODO: in progress
        logger.info('Send message from InlineSendMessage')


class MessageFactory:

    @classmethod
    def get_message_handler(cls, update):
        # when user communicate with the bot from group chat
        if getattr(update, 'inline_query'):
            return InlineMessage
        # when user select some option (by pressing the button)
        elif getattr(update, 'callback_query'):
            return AfterActionMessage
        # when user invoke some bot /command
        return ChatMessage
