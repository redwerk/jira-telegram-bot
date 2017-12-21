from itertools import zip_longest
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from lib import utils
from bot.decorators import login_required

from .base import AbstractCommand
from bot.inlinemenu import build_menu


class WatchDispatcherCommand(AbstractCommand):
    """
    /watch project <name> - Creates a subscription to updates for selected project
    /watch issue <name> - Creates a subscription to updates for selected issue
    If webhook for host hasn't yet - requests to create a one
    """
    targets = ('project', 'issue')
    positive_answer = 'Yes'
    negative_answer = 'No'

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        parameters_names = ('target', 'name')
        description = "<b>Command description:</b>\n" \
                      "/watch issue <i>issue-key</i> - subscribe user to events from selected issue\n" \
                      "/watch project <i>project-key</i> - subscribe user to events from selected project"

        params = dict(zip_longest(parameters_names, options))

        if params['target'] not in self.targets or not params['name']:
            return self.app.send(bot, update, text=description)

        if params['target'] == 'project':
            self.app.jira.is_project_exists(
                host=auth_data.jira_host, project=params['name'], auth_data=auth_data
            )
        elif params['target'] == 'issue':
            self.app.jira.is_issue_exists(
                host=auth_data.jira_host, issue=params['name'], auth_data=auth_data
            )

        host_webhook = self.app.db.search_webhook(auth_data.jira_host)
        if not host_webhook:
            confirmation_buttons = [
                InlineKeyboardButton(text='No', callback_data='create_webhook:{}'.format(self.negative_answer)),
                InlineKeyboardButton(text='Yes', callback_data='create_webhook:{}'.format(self.positive_answer)),
            ]
            buttons = InlineKeyboardMarkup(
                build_menu(confirmation_buttons, n_cols=2)
            )
            text = 'Have no existing webhook for {}. Do you want to create one?\n' \
                   '<b>NOTE:</b> You must have an Administrator permissions for your Jira'.format(auth_data.jira_host)
            return self.app.send(bot, update, text=text, buttons=buttons, simple_message=True)

        CreateSubscribeCommand(self.app).handler(
            bot, update, topic=params['target'], name=params['name'], webhook=host_webhook
        )

    def command_callback(self):
        return CommandHandler('watch', self.handler, pass_args=True)


class CreateWebhookCommand(AbstractCommand):
    """Creates a webhook for JIRA host"""

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        answer = update.callback_query.data.replace('create_webhook:', '')

        if answer == WatchDispatcherCommand.negative_answer:
            return self.app.send(
                bot, update, text='Creating a new webhook was declined', simple_message=True
            )

        webhook_id = str(uuid4())
        status = self.app.db.create_webhook(webhook_id, auth_data.jira_host)

        if status:
            text = utils.generate_webhook_url(webhook_id)
            return self.app.send(bot, update, text=text, simple_message=True)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^create_webhook:')


class CreateSubscribeCommand(AbstractCommand):
    """Creates a subscribe to user for selected updates"""

    def handler(self, bot, update, *args, **kwargs):
        webhook = kwargs.get('webhook')
        topic = kwargs.get('topic')
        name = kwargs.get('name').lower()
        telegram_id = update.message.chat_id

        if self.app.db.get_subscription('{}:{}'.format(telegram_id, name)):
            text = 'You already subscribed on this updates'
            return self.app.send(bot, update, text=text, simple_message=True)

        user = self.app.db.get_user_data(update.message.chat_id)

        data = {
            'sub_id': '{}:{}'.format(telegram_id, name),
            'user_id': user.get('_id'),
            'webhook_id': webhook.get('_id'),
            'topic': topic,
            'name': name,
        }

        status = self.app.db.create_subscription(data)
        if status:
            text = 'Now you will be notified about updates from {}'.format(name.upper())
            return self.app.send(bot, update, text=text, simple_message=True)

        text = "We can't subscribe you on updates at this moment"
        self.app.send(bot, update, text=text, simple_message=True)


class UnwatchDispatcherCommand(AbstractCommand):
    """
    /unwatch project <name> - Unsubscribe from a selected project updates
    /unwatch issue <name> - Unsubscribe from a selected issue updates
    /unwatch list - Return list of all subscriptions TODO
    /unwatch - Unsubscribe from all updates
    """
    targets = ('project', 'issue')

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        parameters_names = ('target', 'name')
        description = ("<b>Command description:</b>\n",
                       "/unwatch project <i>project-key</i> - Unsubscribe from a selected project updates\n",
                       "/unwatch issue <i>issue-key</i> - Unsubscribe from a selected issue updates\n",
                       "/unwatch list - Return list of all subscriptions\n",
                       "/unwatch - Unsubscribe from all updates")
        params = dict(zip_longest(parameters_names, options))

        if not params['target']:
            confirmation_buttons = [
                InlineKeyboardButton(
                    text='No', callback_data='unsubscribe_all:{}'.format(WatchDispatcherCommand.negative_answer)
                ),
                InlineKeyboardButton(
                    text='Yes', callback_data='unsubscribe_all:{}'.format(WatchDispatcherCommand.positive_answer)
                ),
            ]
            buttons = InlineKeyboardMarkup(
                build_menu(confirmation_buttons, n_cols=2)
            )
            text = 'Do you want to unsubscribe from all updates?'
            return self.app.send(bot, update, text=text, buttons=buttons, simple_message=True)

        if params['target'] not in self.targets or not params['name']:
            return self.app.send(bot, update, text=''.join(description), simple_message=True)

        if params['target'] == 'project':
            self.app.jira.is_project_exists(
                host=auth_data.jira_host, project=params['name'], auth_data=auth_data
            )
        elif params['target'] == 'issue':
            self.app.jira.is_issue_exists(
                host=auth_data.jira_host, issue=params['name'], auth_data=auth_data
            )

        kwargs.update({'topic': params['target'], 'name': params['name']})
        UnsubscribeOneItemCommand(self.app).handler(bot, update, **kwargs)

    def command_callback(self):
        return CommandHandler('unwatch', self.handler, pass_args=True)


class UnsubscribeAllUpdatesCommand(AbstractCommand):
    """Allows a user to unsubscribe from all updates"""

    def handler(self, bot, update, *args, **kwargs):
        answer = update.callback_query.data.replace('unsubscribe_all:', '')

        if answer == WatchDispatcherCommand.negative_answer:
            return self.app.send(
                bot, update, text='Unsubscribing from all updates was declined', simple_message=True
            )

        user = self.app.db.get_user_data(update.callback_query.message.chat_id)
        status = self.app.db.delete_all_subscription(user.get('_id'))

        if status:
            text = 'You were unsubscribed from all updates'
            return self.app.send(bot, update, text=text, simple_message=True)

        text = "Can't unsubscribe you from all updates at this moment, please try again later"
        return self.app.send(bot, update, text=text, simple_message=True)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^unsubscribe_all:')


class UnsubscribeOneItemCommand(AbstractCommand):
    """Allows user to unsubscribe from issue or project updates"""

    def handler(self, bot, update, *args, **kwargs):
        topic = kwargs.get('topic')
        name = kwargs.get('name')
        telegram_id = update.message.chat_id

        if not self.app.db.get_subscription('{}:{}'.format(telegram_id, name.lower())):
            text = 'You were not subscribed to {} {} updates'.format(name.upper(), topic.lower())
            return self.app.send(bot, update, text=text, simple_message=True)

        status = self.app.db.delete_subscription('{}:{}'.format(telegram_id, name.lower()))
        if status:
            text = 'You were unsubscribed from {} {} updates'.format(name.upper(), topic.lower())
            return self.app.send(bot, update, text=text, simple_message=True)

        text = "Can't unsubscribe you from {} {} updates, , please try again later".format(name.upper(), topic.lower())
        return self.app.send(bot, update, text=text, simple_message=True)
