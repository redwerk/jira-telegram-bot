from abc import ABCMeta, abstractmethod
import argparse
import logging

from bot.exceptions import ArgumentParserError, ContextValidationError


logger = logging.getLogger('bot')


class CommandArgumentParser(argparse.ArgumentParser):
    """Class for parsing command arguments"""

    def error(self, message):
        raise ArgumentParserError(message)


class AbstractCommand(metaclass=ABCMeta):
    """ Abstract base command class.
    In handler method must be implemented main command logic.
    """
    def __init__(self, app, *args, **kwargs):
        self.app = app

    @abstractmethod
    def handler(self, *args, **kwargs):
        pass

    @property
    def description(self):
        return None

    def command_callback(self):
        # TODO: Move all not main commands to new abstract class
        pass

    def validate_context(self, context):
        """Validate context or raise ContextValidationError.
        This method must be implemented in your command class.
        """
        pass

    def _check_jira(self, options, auth_data):
        """
        Check existence of objects in JIRA (user, status, project) or leave it untouched
        :param options:
        :param auth_data:
        :return:
        """
        pass

    @staticmethod
    def get_argparsers():
        return []

    def parse_arguments(self, args):
        """Parse command arguments

        Arguments:
            args (list): arguments list
            parsers (list): parsers list
        Returns:
            Namedtuple or None
        """
        parsers = self.get_argparsers()
        for parser in parsers:
            try:
                result = parser.parse_args(args)
            except ArgumentParserError:
                continue
            else:
                return result

        return None

    def resolve_arguments(self, arguments, auth_data, verbose=False):
        options = self.parse_arguments(arguments)
        if not options or not options.target:
            if verbose:
                self.validate_context(arguments)
            else:
                raise ContextValidationError(self.description)
        self._check_jira(options, auth_data)
        return options


class AbstractCommandFactory(metaclass=ABCMeta):
    """ Abstract base command factory class.
    Methods command and command_callback must implemented in subclasses.
    """
    commands = dict()

    def __init__(self, app, *args, **kwargs):
        self.app = app

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

        return command(self.app)
