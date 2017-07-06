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
            user = self._bot_instance.db.get_user_data(user_id=chat_id)
            allowed_hosts = user.get('allowed_hosts')

            # bind the jira host to the user
            if jira_host.get('_id') not in allowed_hosts:
                allowed_hosts.append(jira_host.get('_id'))
                self._bot_instance.db.update_user(telegram_id=chat_id, user_data={'allowed_hosts': allowed_hosts})

            data = {
                'consumer_key': jira_host.get('consumer_key'),
                'public_key': utils.get_public_key(jira_host.get('key_sert'))
            }
            message = 'The host is already added to the database, but it is not activated. ' \
                      'To activate the host, add the following information to the Application links.\n' \
                      '<b>NOTE:</b> you must have administrator permissions\n\n' \
                      '<b>Consumer Key:</b> {consumer_key}\n' \
                      '<b>Public Key:</b> {public_key}\n\n' \
                      'This host was attached to you. After adding the specified data try to ' \
                      'authorize via the command /login'.format(**data)

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


class AddHostCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        AddHostCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('add_host', self.command, pass_args=True)


class AddHostProcessCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        Validates Jira host URL, generates RSA-key pairs, saves  keys into server,
        returns consumer key, public key and link on Flask OAuth service
        """
        # TODO: verify the validity of the jira host
        # TODO: generating RSA-key pairs
        # TODO: saving key pairs into the server
        # TODO: creates a new record in the host collection
        scope = self._bot_instance.get_query_scope(update)
        host_url = scope['data'].replace('add_host:', '')

        if host_url == AddHostCommand.negative_answer:
            bot.edit_message_text(
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
                text='Request for adding a new host was declined',
            )
            return

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Host: {}'.format(host_url),
        )


class AddHostProcessCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        AddHostProcessCommand(self._bot_instance).handler(bot, update, *args, **kwargs)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^add_host:')
