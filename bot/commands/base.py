from abc import ABCMeta, abstractmethod


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
        if not hasattr(self, commands) or not isinstance(self.commands, dict):
            raise AttributeError("commands not implemented or is not dict type!")

        command = self.commands.get(cmd)
        # Validation command
        if command is None:
            raise KeyError("Command {} not exists!".format(cmd))

        return command(self._bot_instance)
