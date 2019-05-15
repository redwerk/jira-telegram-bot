from collections import namedtuple
import logging
import sys
import traceback

from decouple import config
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import Updater

from lib import utils
from lib.db import MongoBackend
import bot.commands as commands

from .backends import JiraBackend
from .messages import MessageFactory
from .schedules import Scheduler
from .exceptions import BaseJTBException, BotAuthError, SendMessageHandlerError, JiraReceivingDataException


logger = logging.getLogger('bot')


class JTBApp:
    """Bot to integrate with the JIRA service"""
    __commands = [
        commands.HelpCommand,
        commands.StartCommand,
        commands.ListUnresolvedIssuesCommand,
        commands.ListStatusIssuesCommand,
        commands.UserStatusIssuesCommand,
        commands.ProjectStatusIssuesCommand,
        commands.TimeTrackingDispatcher,
        commands.FilterDispatcherCommand,
        commands.FilterIssuesCommand,
        commands.WatchDispatcherCommand,
        commands.CreateWebhookCommand,
        commands.UnwatchDispatcherCommand,
        commands.UnsubscribeAllUpdatesCommand,
        commands.BasicLoginCommand,
        commands.OAuthLoginCommand,
        commands.DisconnectMenuCommand,
        commands.DisconnectCommand,
        commands.ContentPaginatorCommand,
        commands.ScheduleCommand,
        commands.ScheduleCommandList,
        commands.ScheduleCommandDelete
    ]

    def __init__(self):
        self.updater = Updater(
            config('BOT_TOKEN'),
            workers=config('WORKERS', cast=int, default=3)
        )

        self.db = MongoBackend()
        self.jira = JiraBackend()
        self.AuthData = namedtuple('AuthData', 'auth_method jira_host username credentials')

        for command in self.commands:
            cb = command(self).command_callback()
            self.updater.dispatcher.add_handler(cb)

        self.updater.dispatcher.add_error_handler(self.error_callback)

    @staticmethod
    def send(bot, update, **kwargs):
        message_handler = MessageFactory.get_message_handler(update)
        if not message_handler:
            raise SendMessageHandlerError('Unable to get the handler')
        return message_handler(bot, update, **kwargs).send()

    def run_scheduler(self):
        queue = self.updater.job_queue
        bot = self.updater.bot
        scheduler = Scheduler(self, bot, queue)
        self.updater._init_thread(scheduler.run, "scheduler")

    def start(self):
        self.updater.start_polling()
        self.run_scheduler()
        logger.debug("Jira bot started successfully!")
        self.updater.idle()

    @property
    def commands(self):
        return self.__commands

    def authorization(self, telegram_id):
        """
        Gets the user data and tries to log in according to the specified authorization method.
        Output of messages according to missing information
        :param telegram_id: user id telegram
        :return: returns a namedtuple for further authorization or bool and messages
        TODO: make refactoring in the future
        """
        user_data = self.db.get_user_data(telegram_id)
        auth_method = user_data.get('auth_method')

        if not auth_method:
            raise BotAuthError(
                'You are not authorized by any of the methods (user/pass or OAuth)'
            )
        else:
            if auth_method == 'basic':
                credentials = (
                    user_data.get('username'),
                    utils.decrypt_password(user_data.get('auth')['basic']['password'])
                )
            else:
                host_data = self.db.get_host_data(user_data.get('host_url'))
                if not host_data:
                    raise BotAuthError(
                        'In database there are no data on the {} host'.format(user_data.get('host_url'))
                    )
                credentials = {
                    'access_token': user_data.get('auth')['oauth']['access_token'],
                    'access_token_secret': user_data.get('auth')['oauth']['access_token_secret'],
                    'consumer_key': host_data.get('consumer_key'),
                    'key_cert': utils.read_rsa_key(config('PRIVATE_KEY_PATH'))
                }

            auth_data = self.AuthData(
                auth_method,
                user_data.get('host_url'),
                user_data.get('username'),
                credentials
            )
            self.jira.check_authorization(
                auth_data.auth_method,
                auth_data.jira_host,
                auth_data.credentials,
                base_check=True
            )

            return auth_data

    def error_callback(self, bot, update, error):
        if config("DEBUG", False):
            traceback.print_exc(file=sys.stdout)
        try:
            raise error
        except (NetworkError, TimedOut, JiraReceivingDataException) as e:
            logger.error(
                f"User={update.effective_user.username} Message={update.effective_message.text} Error={e.message})"
            )
            self.send(bot, update, text="Something went wrong. Check your request or network.")
            self.send(bot, update, text=self.commands[0].description)
        except BaseJTBException as e:
            self.send(bot, update, text=e.message)
        except Exception as e:
            logger.critical(
                f"User={update.effective_user.username} Message={update.effective_message.text} Exception={e})"
            )
