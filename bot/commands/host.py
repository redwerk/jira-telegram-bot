from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import utils
from bot.commands.auth import UserOAuthCommand
from bot.commands.base import AbstractCommand, AbstractCommandFactory


class AddHostCommand(AbstractCommand):
    negative_answer = 'No'

    def handler(self, bot, update, *args, **kwargs):
        """
        Adds a new host into a system. If a host is already in DB - returns a link for authorizing via Flask service.
        If not - request for adding a new host into DB.
        """
        chat_id = update.message.chat_id
        data = kwargs.get('args')[0]

        if not data:
            return

        if not utils.validates_hostname(data):
            bot.send_message(
                chat_id=chat_id,
                text='<b>Wrong format.</b> Use the following format:\n'
                     'https://jira.redwerk.com (without the last slash)',
                parse_mode=ParseMode.HTML
            )
            return

        jira_host = self._bot_instance.db.get_host_data(data)

        if jira_host and jira_host.get('is_confirmed'):
            message = 'Follow the link to confirm authorization\n{}'.format(
                UserOAuthCommand.generate_auth_link(telegram_id=chat_id, host_url=jira_host.get('url'))
            )
            bot.send_message(
                chat_id=chat_id,
                text=message,
            )
            return

        elif jira_host:
            message = self.get_app_links_data(bot, jira_host, chat_id)
            bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            return

        else:
            button_list = [
                InlineKeyboardButton(
                    'Yes', callback_data='add_host:{}'.format(data)
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
                text='This host is not supported at this time, '
                     'do you want to go through the procedure of adding a new host?\n'
                     '<b>NOTE:</b> for add a generated data into Jira you must have administrator permissions',
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
            'public_key': utils.get_public_key(jira_host.get('key_sert')),
            'application_url': config('OAUTH_SERVICE_URL')
        }
        message = 'The host is already added to the database, but it is not activated. ' \
                  'To activate the host, add the following information to the Application links.\n' \
                  '<b>NOTE:</b> you must have administrator permissions\n\n' \
                  '<b>Consumer Key:</b> {consumer_key}\n' \
                  '<b>Public Key:</b> {public_key}\n' \
                  '<b>Application URL:</b> {application_url}\n\n' \
                  'This host was attached to you. After adding the specified data try to ' \
                  'authorize via the command /login'.format(**data)

        return message


class AddHostCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        AddHostCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('add_host', self.command, pass_args=True)


class AddHostProcessCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        Validates Jira host URL, generates RSA private key, saves key into server,
        returns consumer key, public key and link on Flask OAuth service
        """
        scope = self._bot_instance.get_query_scope(update)
        host_url = scope['data'].replace('add_host:', '')
        message = 'Failed to create a new host'

        if host_url == AddHostCommand.negative_answer:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='Request for adding a new host was declined',
            )
            return

        if not utils.is_jira_app(host_url):
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text="It's not a Jira application",
            )
            return

        host_data = {
            'url': host_url,
            'readable_name': utils.generate_readable_name(host_url),
            'consumer_key': utils.generate_consumer_key(host_url),
            'key_sert': utils.generate_key_name(host_url),
            'is_confirmed': False
        }

        host_status = self._bot_instance.db.create_host(host_data)

        if host_status:
            created_host = self._bot_instance.db.get_host_data(host_url)
            key_status = utils.generate_private_key(created_host.get('key_sert'))

            if key_status:
                message = AddHostCommand(self._bot_instance).get_app_links_data(bot, created_host, scope['chat_id'])

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=message,
            parse_mode=ParseMode.HTML
        )


class AddHostProcessCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        AddHostProcessCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^add_host:')
