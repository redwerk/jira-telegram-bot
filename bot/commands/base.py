from abc import ABCMeta, abstractmethod
import logging
from telegram import ParseMode

from common import utils
from common.exceptions import SendMessageHandlerError
from common.db import MongoBackend


# TODO: remove logger after testing!
logger = logging.getLogger()

# Message types
BASE = 'base'
AFTER_ACTION = 'after_action'
INLINE = 'inline'


class BaseSendMessage:
    db = MongoBackend()
    issues_per_page = 10
    callback_paginator_key = 'paginator:{}'

    def send(self, bot, update, result, *args, **kwargs):
        pass

    def message_format(self, title, items):
        pass

    def get_metadata(self, update):
        pass


class ChatSendMessage(BaseSendMessage):

    def send(self, bot, update, result, *args, **kwargs):
        logger.info('ChatSendMessage: {:.30}...'.format(result.get('text', 'Test')))
        chat_id = self.get_metadata(update)

        if kwargs.get('simple_message'):
            bot.send_message(
                chat_id=chat_id,
                text=result.get('text'),
                reply_markup=result.get('buttons'),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        elif kwargs.get('items'):
            title = result.get('title')
            items = result.get('items')

            if len(items) > self.issues_per_page:
                text, buttons = self.processing_multiple_pages(title, items, result)
            else:
                text, buttons = self.processing_single_page(title, items, result)

            bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            logging.error('Formatting type not passed')

    def message_format(self, title, items):
        f_title = '<b>{}</b>\n\n'.format(title)
        f_issues = '\n\n'.join(items)
        return f_title + f_issues

    def get_metadata(self, update):
        return update.message.chat_id

    def save_into_cache(self, title, splitted_data, key):
        page_count = len(splitted_data)
        status = self.db.create_cache(key, title, splitted_data, page_count)

        if not status:
            logging.exception('An attempt to write content to the cache failed: {}'.format(key))

    def processing_multiple_pages(self, title, items, result):
        callback_key = self.callback_paginator_key.format(result.get('key'))
        splitted_data = utils.split_by_pages(items, self.issues_per_page)
        self.save_into_cache(title, splitted_data, result.get('key'))

        text = self.message_format(title, splitted_data[0])  # return first page
        buttons = utils.get_pagination_keyboard(
            current=1,
            max_page=len(splitted_data),
            str_key=callback_key + '#{}'
        )

        return text, buttons

    def processing_single_page(self, title, items, result):
        buttons = None
        callback_key = self.callback_paginator_key.format(result.get('key'))
        text = self.message_format(title, items)

        if result.get('page') and result.get('page_count'):
            buttons = utils.get_pagination_keyboard(
                current=result.get('page'),
                max_page=result.get('page_count'),
                str_key=callback_key + '#{}'
            )

        return text, buttons


class AfterActionSendMessage(ChatSendMessage):

    def send(self, bot, update, result, *args, **kwargs):
        logger.info('AfterActionSendMessage: {:.30}...'.format(result.get('text', 'Test')))
        chat_id, message_id = self.get_metadata(update)

        if kwargs.get('simple_message'):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=result.get('text'),
                reply_markup=result.get('buttons'),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        elif kwargs.get('items'):
            title = result.get('title')
            items = result.get('items')

            if len(items) > self.issues_per_page:
                text, buttons = self.processing_multiple_pages(title, items, result)
            else:
                text, buttons = self.processing_single_page(title, items, result)

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            logging.error('Formatting type not passed')

    def get_metadata(self, update):
        query = update.callback_query
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return chat_id, message_id


class InlineSendMessage(BaseSendMessage):

    def send(self, bot, update, result, *args, **kwargs):
        logger.info('InlineSendMessage: {:.30}...'.format(result.get('text')))
        print('send message from InlineSendMessage')


class SendMessageFactory:
    message_handlers = {
        BASE: ChatSendMessage(),
        AFTER_ACTION: AfterActionSendMessage(),
        INLINE: InlineSendMessage()
    }

    def send(self, message_type, bot, update, result, *args, **kwargs):
        handler = self.message_handlers.get(message_type)

        if not handler:
            raise SendMessageHandlerError('Unable to get the handler')

        handler.send(bot, update, result, *args, **kwargs)


class AbstractCommand(metaclass=ABCMeta):
    """ Abstract base command class.
    In hendler method must be implemented main command logic.
    """
    send_factory = SendMessageFactory()

    def __init__(self, bot_instance, *args, **kwargs):
        self._bot_instance = bot_instance

    @abstractmethod
    def handler(self, *args, **kwargs):
        # Must be implemented
        pass

    def command_callback(self):
        # Must be implemented
        pass

    def get_message_type(self, update):
        # when user communicate with the bot from group chat
        if getattr(update, 'inline_query'):
            return INLINE
        # when user select some option (by pressing the button)
        elif getattr(update, 'callback_query'):
            return AFTER_ACTION
        # when user invoke some bot /command
        else:
            return BASE


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
