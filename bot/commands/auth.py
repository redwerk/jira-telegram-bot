import os
from string import Template

from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from common import utils
from common.errors import BotAuthError, JiraConnectionError, JiraLoginError

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
            text='Follow the link to confirm authorization\n{}'.format(service_url),
        )

    @staticmethod
    def generate_auth_link(telegram_id: int, host_url: str) -> str:
        return '{}/authorize/{}/?host={}'.format(config('OAUTH_SERVICE_URL'), telegram_id, host_url)


class OAuthCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        UserOAuthCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^oauth:')


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
    negative_answer = 'No'

    def handler(self, bot, update, *args, **kwargs):
        """
        Adds a new host into a system. If a host is already in DB - returns a link for authorizing via Flask service.
        If not - request for adding a new host into DB.
        """
        chat_id = update.message.chat_id
        auth_options = kwargs.get('args')

        if not auth_options:
            bot.send_message(
                chat_id=chat_id,
                text='Host is required option'
            )
            return

        domain_name = kwargs.get('args')[0]
        user_data = self._bot_instance.db.get_user_data(chat_id)
        try:
            auth = self._bot_instance.get_and_check_cred(chat_id)
        except (JiraLoginError, JiraConnectionError) as e:
            bot.send_message(chat_id=chat_id, text=e.message)
            return
        except BotAuthError:
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

        if jira_host:
            message = 'Follow the link to confirm authorization\n{}'.format(
                UserOAuthCommand.generate_auth_link(telegram_id=chat_id, host_url=jira_host.get('url'))
            )
            bot.send_message(
                chat_id=chat_id,
                text=message,
            )
            return

        else:
            button_list = [
                InlineKeyboardButton(
                    'Yes', callback_data='add_host:{}'.format(domain_name)
                ),
                InlineKeyboardButton(
                    'No', callback_data='add_host:{}'.format(self.negative_answer)
                ),
            ]

            reply_markup = InlineKeyboardMarkup(utils.build_menu(
                button_list, n_cols=2
            ))

            bot.send_message(
                chat_id=chat_id,
                text='This host is not supported at the moment, '
                     'do you want to go through the procedure of adding a new host?\n'
                     '<b>NOTE:</b> you must have administrator permissions to add a generated data into Jira',
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return

    def get_app_links_data(self, bot, jira_host, chat_id):
        user = self._bot_instance.db.get_user_data(user_id=chat_id)
        allowed_hosts = user.get('allowed_hosts')

        # bind the jira host to the user
        if jira_host.get('_id') not in allowed_hosts:
            allowed_hosts.append(jira_host.get('_id'))
            self._bot_instance.db.update_user(telegram_id=chat_id, user_data={'allowed_hosts': allowed_hosts})

        data = {
            'consumer_key': jira_host.get('consumer_key'),
            'public_key': utils.read_rsa_key(config('PUBLIC_KEY_PATH')),
            'application_url': config('OAUTH_SERVICE_URL'),
            'application_name': 'JiraTelegramBot',
        }

        src_text = None
        with open(os.path.join(config('DOCS_PATH'), 'app_links.txt')) as file:
            src_text = Template(file.read())

        return src_text.substitute(data)


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


class AddHostProcessCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        Validates Jira host URL, returns consumer key, public key and link on Flask OAuth service
        """
        scope = self._bot_instance.get_query_scope(update)
        host_url = scope['data'].replace('add_host:', '')
        message = 'Failed to create a new host'

        if host_url == OAuthLoginCommand.negative_answer:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='Request for adding a new host was declined',
            )
            return

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Processing...',
        )

        host_url = self.check_hosturl(host_url)

        if not host_url:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text="This is not Jira host. "
                     "Please try again or use /feedback command so we can help you to fix this issue",
            )
            return

        host_data = {
            'url': host_url,
            'readable_name': utils.generate_readable_name(host_url),
            'consumer_key': utils.generate_consumer_key(),
            'is_confirmed': False
        }

        host_status = self._bot_instance.db.create_host(host_data)

        if host_status:
            created_host = self._bot_instance.db.get_host_data(host_url)
            message = OAuthLoginCommand(self._bot_instance).get_app_links_data(bot, created_host, scope['chat_id'])

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=message,
            parse_mode=ParseMode.HTML
        )

    def check_hosturl(self, host_url):
        if utils.validates_hostname(host_url):
            return host_url

        elif not utils.validates_hostname(host_url):
            for protocol in ('https://', 'http://'):
                test_host_url = '{}{}'.format(protocol, host_url)

                if self._bot_instance.jira.is_jira_app(test_host_url):
                    return test_host_url
            else:
                return False


class AddHostProcessCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        AddHostProcessCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^add_host:')


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
        except (JiraLoginError, JiraConnectionError) as e:
            bot.send_message(chat_id=chat_id, text=e.message)
            return
        except BotAuthError:
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
        host_url = AddHostProcessCommand(self._bot_instance).check_hosturl(host)
        if not host_url:
            bot.send_message(
                chat_id=chat_id,
                text='This is not a Jira application. Please try again',
            )
            return

        try:
            self._bot_instance.jira.check_authorization(
                auth_method='basic',
                jira_host=host_url,
                credentials=(username, password),
                base_check=True,
            )
        except (JiraConnectionError, JiraLoginError) as e:
            bot.send_message(chat_id=chat_id, text=e.message)
            return

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
