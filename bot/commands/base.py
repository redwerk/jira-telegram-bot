from abc import ABCMeta, abstractmethod
from common.exceptions import SendMessageHandlerError


# Message types
BASE = 'base'
AFTER_ACTION = 'after_action'
INLINE = 'inline'


class BaseSendMessage:

    def send(self, bot, update, result, *args, **kwargs):
        pass

    def message_format(self, result):
        pass

    def get_metadata(self, update):
        pass


class ChatSendMessage(BaseSendMessage):

    def send(self, bot, update, result, *args, **kwargs):
        chat_id = self.get_metadata(update)

        if kwargs.get('simple_message'):
            bot.send_message(
                chat_id=chat_id,
                text=result.get('text')
            )
        elif kwargs.get('with_buttons'):
            bot.send_message(
                chat_id=chat_id,
                text=result.get('text'),
                reply_markup=result.get('buttons')
            )

    def message_format(self, result):
        pass

    def get_metadata(self, update):
        return update.message.chat_id


class AfterActionSendMessage(ChatSendMessage):

    def send(self, bot, update, result, *args, **kwargs):
        chat_id, message_id = self.get_metadata(update)

        if kwargs.get('simple_message'):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=result.get('text')
            )
        elif kwargs.get('with_buttons'):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=result.get('text'),
                reply_markup=result.get('buttons')
            )

    def get_metadata(self, update):
        query = update.callback_query
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        return chat_id, message_id


class InlineSendMessage(BaseSendMessage):

    def send(self, bot, update, result, *args, **kwargs):
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
