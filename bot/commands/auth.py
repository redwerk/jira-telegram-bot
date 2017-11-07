import os
from string import Template

from decouple import config
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from common import utils
from common.exceptions import BotAuthError

from .base import AbstractCommand, AbstractCommandFactory


class DisconnectMenuCommand(AbstractCommand):
    """
    /disconnect - request to delete credentials from the database
    """
    positive_answer = 'Yes'
    negative_answer = 'No'

    def handler(self, bot, update, *args, **kwargs):
        """
        /disconnect
        """
        message_type = self.get_message_type(update)
        result = dict()

        button_list = [
            InlineKeyboardButton(
                'Yes', callback_data='disconnect:{}'.format(self.positive_answer)
            ),
            InlineKeyboardButton(
                'No', callback_data='disconnect:{}'.format(self.negative_answer)
            ),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        result['text'] = 'Are you sure you want to log out? All credentials associated with this user will be lost.'
        result['buttons'] = reply_markup
        self.send_factory.send(message_type, bot, update, result, with_buttons=True)

    def command_callback(self):
        return CommandHandler('disconnect', self.handler)


class DisconnectCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Deletes user credentials from DB"""
        scope = self._bot_instance.get_query_scope(update)
        answer = scope['data'].replace('disconnect:', '')
        message_type = self.get_message_type(update)
        result = dict()

        if answer == DisconnectMenuCommand.positive_answer:
            reset_dict = {
                'username': None,
                'host_url': None,
                'auth_method': None,
                'auth.oauth.access_token': None,
                'auth.oauth.access_token_secret': None,
                'auth.basic.password': None,
            }
            status = self._bot_instance.db.update_user(scope['telegram_id'], reset_dict)

            if status:
                result['text'] = 'Credentials were successfully reset.'
                self.send_factory.send(message_type, bot, update, result, simple_message=True)
                return
            else:
                result['text'] = 'Credentials were not removed from the database, please try again later.'
                self.send_factory.send(message_type, bot, update, result, simple_message=True)
                return

        else:
            result['text'] = 'Resetting credentials was not confirmed'
            self.send_factory.send(message_type, bot, update, result, simple_message=True)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^disconnect:')


class OAuthLoginCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        If the host does not exist - generating data for creating an Application link in Jira, displaying the data
        to the user and displaying a link for authorization.
        If the host exists and is confirmed (successfully logged in) - return the link for authorization.
        If the host exists but is not confirmed - generating a new consumer key, displaying the data for
        creating the Application link and displaying the link for authorization
        """
        chat_id = update.message.chat_id
        auth_options = kwargs.get('args')
        result = dict()
        message_type = self.get_message_type(update)

        if not auth_options:
            result['text'] = 'Host is required option'
            self.send_factory.send(message_type, bot, update, result, simple_message=True)
            return

        domain_name = auth_options[0]
        user_data = self._bot_instance.db.get_user_data(chat_id)
        try:
            auth = self._bot_instance.get_and_check_cred(chat_id)
        except BotAuthError:
            # ignore authorization check
            pass
        else:
            if user_data.get('auth_method') or auth:
                result['text'] = 'You are already connected to {}. ' \
                                 'Please use /disconnect before connecting ' \
                                 'to another JIRA instance.'.format(user_data.get('host_url'))
                self.send_factory.send(message_type, bot, update, result, simple_message=True)
                # bot.send_message(
                #     chat_id=chat_id,
                #     text='You are already connected to {}. '
                #          'Please use /disconnect before connecting '
                #          'to another JIRA instance.'.format(user_data.get('host_url')),
                # )
                return

        if not utils.validates_hostname(domain_name):
            jira_host = self._bot_instance.db.search_host(domain_name)
        else:
            jira_host = self._bot_instance.db.get_host_data(domain_name)

        if jira_host and jira_host.get('is_confirmed'):
            result['text'] = 'Follow the <a href="{}">link</a> to confirm authorization'.format(
                self.generate_auth_link(chat_id, jira_host.get('url'))
            )
        elif jira_host and not jira_host.get('is_confirmed'):
            jira_host.update({'consumer_key': utils.generate_consumer_key()})
            host_updated = self._bot_instance.db.update_host(host_url=jira_host.get('url'), host_data=jira_host)

            if host_updated:
                # sends data for creating an Application link
                result['text'] = self.get_app_links_data(jira_host)
                self.send_factory.send(message_type, bot, update, result, simple_message=True)
                # sends a link for authorization via OAuth
                result['text'] = 'Follow the <a href="{}">link</a> to confirm authorization'.format(
                    self.generate_auth_link(chat_id, jira_host.get('url'))
                )
        else:
            domain_name = self.check_hosturl(domain_name)

            if not domain_name:
                bot.send_message(chat_id=chat_id, text="This is not a Jira application. Please try again")
                return

            host_data = {
                'url': domain_name,
                'is_confirmed': False,
                'consumer_key': utils.generate_consumer_key(),
            }

            host_status = self._bot_instance.db.create_host(host_data)

            if host_status:
                # sends data for creating an Application link
                result['text'] = self.get_app_links_data(jira_host)
                self.send_factory.send(message_type, bot, update, result, simple_message=True)
                # sends a link for authorization via OAuth
                result['text'] = 'Follow the <a href="{}">link</a> to confirm authorization'.format(
                    self.generate_auth_link(chat_id, host_data.get('url'))
                )

        self.send_factory.send(message_type, bot, update, result, simple_message=True)

    def generate_auth_link(self, telegram_id, host_url):
        return '{}/authorize/{}/?host={}'.format(config('OAUTH_SERVICE_URL'), telegram_id, host_url)

    def get_app_links_data(self, jira_host):
        data = {
            'consumer_key': jira_host.get('consumer_key'),
            'public_key': utils.read_rsa_key(config('PUBLIC_KEY_PATH')),
            'application_url': config('OAUTH_SERVICE_URL'),
            'application_name': 'JiraTelegramBot',
        }

        with open(os.path.join(config('DOCS_PATH'), 'app_links.txt')) as file:
            src_text = Template(file.read())

        return src_text.substitute(data)

    def check_hosturl(self, host_url):
        valid = utils.validates_hostname(host_url)

        if valid and self._bot_instance.jira.is_jira_app(host_url):
            return host_url
        elif not valid:
            for protocol in ('https://', 'http://'):
                test_host_url = '{}{}'.format(protocol, host_url)

                if self._bot_instance.jira.is_jira_app(test_host_url):
                    return test_host_url
            else:
                return False


class OAuthLoginCommandFactory(AbstractCommandFactory):
    """/oauth <host> - Login into Jira via OAuth method"""

    def command(self, bot, update, *args, **kwargs):
        telegram_id = update.message.chat_id
        user_exists = self._bot_instance.db.is_user_exists(telegram_id)

        if not user_exists:
            bot.send_message(
                chat_id=telegram_id,
                text='You are not in the database. Just call the /start command',
            )
            return

        OAuthLoginCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('oauth', self.command, pass_args=True)


class BasicLoginCommand(AbstractCommand):
    """/connect <host> <username> <password> - Login into Jira via username and password"""

    def handler(self, bot, update, *args, **kwargs):
        message_type = self.get_message_type(update)
        result = dict()
        chat_id = update.message.chat_id
        auth_options = kwargs.get('args')

        if not auth_options:
            # if no parameters are passed
            result['text'] = 'You did not specify parameters for authorization'
            self.send_factory.send(message_type, bot, update, result, simple_message=True)
            return

        user_data = self._bot_instance.db.get_user_data(chat_id)
        try:
            auth = self._bot_instance.get_and_check_cred(chat_id)
        except BotAuthError:
            # ignore authorization check
            pass
        else:
            if user_data.get('auth_method') or auth:
                result['text'] = 'You are already connected to {}. ' \
                                 'Please use /disconnect before connecting ' \
                                 'to another JIRA instance.'.format(user_data.get('host_url'))
                self.send_factory.send(message_type, bot, update, result, simple_message=True)
                return

        try:
            host, username, password = auth_options
        except ValueError:
            # if not passed all the parameters
            result['text'] = 'You have not specified all the parameters for authorization. ' \
                             'Try again using the following instructions:\n' \
                             '/connect <host> <username> <password>'
            self.send_factory.send(message_type, bot, update, result, simple_message=True)
            return

        # getting the URL to the Jira app
        host_url = OAuthLoginCommand(self._bot_instance).check_hosturl(host)
        if not host_url:
            result['text'] = 'This is not a Jira application. Please try again'
            self.send_factory.send(message_type, bot, update, result, simple_message=True)
            return

        self._bot_instance.jira.check_authorization(
            auth_method='basic',
            jira_host=host_url,
            credentials=(username, password),
            base_check=True,
        )

        basic_auth = {
            'host_url': host_url,
            'username': username,
            'auth_method': 'basic',
            'auth.basic.password': utils.encrypt_password(password)
        }

        status = self._bot_instance.db.update_user(chat_id, basic_auth)
        if status:
            result['text'] = 'You were successfully authorized in {}'.format(host_url)
            self.send_factory.send(message_type, bot, update, result, simple_message=True)
        else:
            result['text'] = 'Failed to save data to database, please try again later'
            self.send_factory.send(message_type, bot, update, result, simple_message=True)


class BasicLoginCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        telegram_id = update.message.chat_id
        user_exists = self._bot_instance.db.is_user_exists(telegram_id)

        if not user_exists:
            bot.send_message(
                chat_id=telegram_id,
                text='You are not in the database. Just call the /start command',
            )
            return

        BasicLoginCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('connect', self.command, pass_args=True)
