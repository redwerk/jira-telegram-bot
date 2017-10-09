import os
from string import Template

from decouple import config
from telegram import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from common import utils
from common.exceptions import BotAuthError

from .base import AbstractCommand, AbstractCommandFactory
from .menu import DisconnectMenuCommand


class UserOAuthCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Command generates URL for further authorization via Flask OAuth service"""
        scope = self._bot_instance.get_query_scope(update)
        host_url = scope['data'].replace('oauth:', '')
        host = self._bot_instance.db.get_host_data(host_url)

        service_url = self.generate_auth_link(scope['telegram_id'], host['url'])

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Follow the <a href="{}">link</a> to confirm authorization'.format(service_url),
        )

    @staticmethod
    def generate_auth_link(telegram_id: int, host_url: str) -> str:
        return '{}/authorize/{}/?host={}'.format(config('OAUTH_SERVICE_URL'), telegram_id, host_url)


class DisconnectMenuCommandFactory(AbstractCommandFactory):
    """
    /disconnect - request to delete credentials from the database
    """
    def command(self, bot, update, *args, **kwargs):
        DisconnectMenuCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('disconnect', self.command)


class DisconnectCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Deletes user credentials from DB"""
        scope = self._bot_instance.get_query_scope(update)
        answer = scope['data'].replace('disconnect:', '')

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
                bot.edit_message_text(
                    chat_id=scope['chat_id'],
                    message_id=scope['message_id'],
                    text='Credentials were successfully reset.',
                )
                return
            else:
                bot.edit_message_text(
                    chat_id=scope['chat_id'],
                    message_id=scope['message_id'],
                    text='Credentials were not removed from the database, please try again later.',
                )
                return

        else:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='Resetting credentials was not confirmed',
            )
            return


class DisconnectCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        DisconnectCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^disconnect:')


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
        message = 'Failed to create a new host'

        if not auth_options:
            bot.send_message(chat_id=chat_id, text='Host is required option')
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
                bot.send_message(
                    chat_id=chat_id,
                    text='You are already connected to {}. '
                         'Please use /disconnect before connecting '
                         'to another JIRA instance.'.format(user_data.get('host_url')),
                )
                return

        if not utils.validates_hostname(domain_name):
            jira_host = self._bot_instance.db.search_host(domain_name)
        else:
            jira_host = self._bot_instance.db.get_host_data(domain_name)

        if jira_host and jira_host.get('is_confirmed'):
            message = 'Follow the <a href="{}">link</a> to confirm authorization'.format(
                UserOAuthCommand.generate_auth_link(telegram_id=chat_id, host_url=jira_host.get('url'))
            )
        elif jira_host and not jira_host.get('is_confirmed'):
            jira_host.update({'consumer_key': utils.generate_consumer_key()})
            host_updated = self._bot_instance.db.update_host(host_url=jira_host.get('url'), host_data=jira_host)

            if host_updated:
                # sends data for creating an Application link
                bot.send_message(chat_id=chat_id, text=self.get_app_links_data(jira_host), parse_mode=ParseMode.HTML)
                # sends a link for authorization via OAuth
                message = 'Follow the <a href="{}">link</a> to confirm authorization'.format(
                    UserOAuthCommand.generate_auth_link(telegram_id=chat_id, host_url=jira_host.get('url'))
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
                bot.send_message(chat_id=chat_id, text=self.get_app_links_data(host_data), parse_mode=ParseMode.HTML)
                # sends a link for authorization via OAuth
                message = 'Follow the <a href="{}">link</a> to confirm authorization'.format(
                    UserOAuthCommand.generate_auth_link(telegram_id=chat_id, host_url=host_data.get('url'))
                )

        bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

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
        chat_id = update.message.chat_id
        auth_options = kwargs.get('args')

        if not auth_options:
            # if no parameters are passed
            bot.send_message(
                chat_id=chat_id,
                text='You did not specify parameters for authorization',
            )
            return

        user_data = self._bot_instance.db.get_user_data(chat_id)
        try:
            auth = self._bot_instance.get_and_check_cred(chat_id)
        except BotAuthError:
            # ignore authorization check
            pass
        else:
            if user_data.get('auth_method') or auth:
                bot.send_message(
                    chat_id=chat_id,
                    text='You are already connected to {}. '
                         'Please use /disconnect before connecting '
                         'to another JIRA instance.'.format(user_data.get('host_url')),
                )
                return

        try:
            host, username, password = auth_options
        except ValueError:
            # if not passed all the parameters
            bot.send_message(
                chat_id=chat_id,
                text='You have not specified all the parameters for authorization. '
                     'Try again using the following instructions:\n'
                     '/connect <host> <username> <password>',
            )
            return

        bot.send_message(
            chat_id=chat_id,
            text='Authorization to <b>{}</b>...'.format(host),
            parse_mode=ParseMode.HTML
        )

        # getting the URL to the Jira app
        host_url = OAuthLoginCommand(self._bot_instance).check_hosturl(host)
        if not host_url:
            bot.send_message(
                chat_id=chat_id,
                text='This is not a Jira application. Please try again',
            )
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
            bot.send_message(
                chat_id=chat_id,
                text='You were successfully authorized in {}'.format(host_url),
            )
        else:
            bot.send_message(
                chat_id=chat_id,
                text='Failed to save data to database, please try again later',
            )


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
