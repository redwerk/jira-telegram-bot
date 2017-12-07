import logging
from abc import ABCMeta, abstractmethod

from telegram import ParseMode

from common import utils
from common.db import MongoBackend
from common.exceptions import SendMessageHandlerError

logger = logging.getLogger()


class BaseSendMessage:
    db = MongoBackend()
    issues_per_page = 10
    callback_paginator_key = 'paginator:{}'

    def __init__(self, bot, update, **kwargs):
        """
        kwargs['title'] - Title of the message (the text is bold)
        kwargs['text'] - Simple text in message (withour editing)
        kwargs['buttons'] - any buttons to show in chat
        kwargs['items'] - list of strings with any data
        kwargs['key'] - key for cached data
        kwargs['page'] - number of page that user clicked (at inline keyboard)
        kwargs['page_count'] - total count of the pages (for generating a new inline keyboard)
        kwargs['raw_items'] - raw JIRA issue objects, need to format before display
        """
        self.bot = bot
        self.update = update
        self.title = kwargs.get('title')
        self.text = kwargs.get('text')
        self.buttons = kwargs.get('buttons')
        self.items = kwargs.get('items')
        self.key = kwargs.get('key')
        self.page = kwargs.get('page')
        self.page_count = kwargs.get('page_count')
        self.simple_message = kwargs.get('simple_message')
        self.raw_items = kwargs.get('raw_items')

    @abstractmethod
    def send(self):
        pass


class ChatSendMessage(BaseSendMessage):

    def send(self):
        chat_id = self.get_metadata()

        if self.simple_message:
            self.bot.send_message(
                chat_id=chat_id,
                text=self.text,
                reply_markup=self.buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        elif self.items or self.raw_items:
            # formatting list of strings from JIRA issue objects
            if self.raw_items:
                self.items = self.issues_format()

            if len(self.items) > self.issues_per_page:
                # if items count more than one page
                text, buttons = self.processing_multiple_pages()
            else:
                text, buttons = self.processing_single_page()

            self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            raise SendMessageHandlerError('Formatting type not passed')

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
        splitted_data = utils.split_by_pages(self.items, self.issues_per_page)
        self.save_into_cache(splitted_data)

        text = self.message_format(splitted_data[0])  # return first page
        buttons = utils.get_pagination_keyboard(
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
            buttons = utils.get_pagination_keyboard(
                current=self.page,
                max_page=self.page_count,
                str_key=callback_key + '#{}'
            )

        return text, buttons


class AfterActionSendMessage(ChatSendMessage):

    def send(self):
        chat_id, message_id = self.get_metadata()

        if self.simple_message:
            self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self.text,
                reply_markup=self.buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        elif self.items or self.raw_items:
            # formatting list of strings from JIRA issue objects
            if self.raw_items:
                self.items = self.issues_format()

            if len(self.items) > self.issues_per_page:
                # if items count more than one page
                text, buttons = self.processing_multiple_pages()
            else:
                text, buttons = self.processing_single_page()

            self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            raise SendMessageHandlerError('Formatting type not passed')

    def get_metadata(self):
        query = self.update.callback_query
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return chat_id, message_id


class InlineSendMessage(BaseSendMessage):

    def send(self):
        # TODO: in progress
        logger.info('Send message from InlineSendMessage')


class SendMessageFactory:

    @classmethod
    def send(cls, bot, update, *args, **kwargs):
        handler = cls.get_message_handler(update)

        if not handler:
            raise SendMessageHandlerError('Unable to get the handler')

        handler(bot, update, **kwargs).send()

    @classmethod
    def get_message_handler(cls, update):
        # when user communicate with the bot from group chat
        if getattr(update, 'inline_query'):
            return InlineSendMessage
        # when user select some option (by pressing the button)
        elif getattr(update, 'callback_query'):
            return AfterActionSendMessage
        # when user invoke some bot /command
        return ChatSendMessage


class AbstractCommand(metaclass=ABCMeta):
    """ Abstract base command class.
    In hendler method must be implemented main command logic.
    """

    def __init__(self, bot_instance, *args, **kwargs):
        self._bot_instance = bot_instance

    @abstractmethod
    def handler(self, *args, **kwargs):
        # Must be implemented
        pass

    def command_callback(self):
        # Must be implemented
        pass


class AbstractCommandFactory(metaclass=ABCMeta):
    """ Abstract base command factory class.
    Methods command and command_callback must implemented in subclasses.
    """
    commands = dict()

    def __init__(self, bot_instance, *args, **kwargs):
        self._bot_instance = bot_instance

    @abstractmethod
    def command(self, bot, update, *args, **kwargs):
        # Must be implemented
        pass

    @abstractmethod
    def command_callback(self):
        # Must be implemented
        pass

    def _command_factory_method(self, cmd):
        # Validation commands list
        if not hasattr(self, "commands") or not isinstance(self.commands, dict):
            raise AttributeError("commands not implemented or is not dict type!")

        command = self.commands.get(cmd)
        # Validation command
        if command is None:
            raise KeyError("Command {} not exists!".format(cmd))

        return command(self._bot_instance)
