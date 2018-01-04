from itertools import zip_longest

from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot.helpers import login_required
from bot.inlinemenu import build_menu

from .base import AbstractCommand


class WatchDispatcherCommand(AbstractCommand):
    """
    /watch project <name> - Creates a subscription to updates for selected project
    /watch issue <name> - Creates a subscription to updates for selected issue
    If webhook for host hasn't yet - requests to create a one
    """
    targets = ('project', 'issue')
    positive_answer = 'Yes'
    negative_answer = 'No'
    description = (
        "<b>Command description:</b>\n"
        "/watch issue <i>issue-key</i> - subscribe user to events from selected issue\n"
        "/watch project <i>project-key</i> - subscribe user to events from selected project"
    )

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        parameters_names = ('target', 'name')
        params = dict(zip_longest(parameters_names, options))

        if params['target'] not in self.targets or not params['name']:
            return self.app.send(bot, update, text=self.description)

        if params['target'] == 'project':
            self.app.jira.is_project_exists(
                host=auth_data.jira_host, project=params['name'], auth_data=auth_data
            )
        elif params['target'] == 'issue':
            self.app.jira.is_issue_exists(
                host=auth_data.jira_host, issue=params['name'], auth_data=auth_data
            )

        host_webhook = self.app.db.get_webhook(host_url=auth_data.jira_host)
        if not host_webhook:
            confirmation_buttons = [
                InlineKeyboardButton(text='No', callback_data='create_webhook:{}'.format(self.negative_answer)),
                InlineKeyboardButton(text='Yes', callback_data='create_webhook:{}'.format(self.positive_answer)),
            ]
            buttons = InlineKeyboardMarkup(
                build_menu(confirmation_buttons, n_cols=2)
            )
            text = (
                f'Have no existing webhook for {auth_data.jira_host}. Do you want to create one?\n'
                '<b>NOTE:</b> You must have an Administrator permissions for your Jira'
            )
            return self.app.send(bot, update, text=text, buttons=buttons)

        CreateSubscribeCommand(self.app).handler(
            bot, update, topic=params['target'], name=params['name'], webhook=host_webhook
        )

    def command_callback(self):
        return CommandHandler('watch', self.handler, pass_args=True)


class CreateWebhookCommand(AbstractCommand):
    """Creates a webhook for JIRA host"""
    message_template = (
        'Follow the <a href="http://telegra.ph/Creating-the-Webhook-for-JiraBot-in-Jira-12-22">'
        'instructions</a> and use the link to create a WebHook in your Jira\n\n'
        'Your link: {}')

    def generate_webhook_url(self, webhook_id):
        """Generates a Webhook URL for processing updates"""
        host = config('OAUTH_SERVICE_URL')
        return '{0}/webhook/{1}'.format(host, webhook_id) + '/${project.key}/${issue.key}'

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        answer = update.callback_query.data.replace('create_webhook:', '')

        if answer == WatchDispatcherCommand.negative_answer:
            return self.app.send(bot, update, text='Creating a new webhook was declined')

        webhook_id = self.app.db.create_webhook(auth_data.jira_host)
        if webhook_id:
            text = self.message_template.format(self.generate_webhook_url(webhook_id))
            return self.app.send(bot, update, text=text)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^create_webhook:')


class CreateSubscribeCommand(AbstractCommand):
    """Creates a subscribe to user for selected updates"""

    def handler(self, bot, update, *args, **kwargs):
        webhook = kwargs.get('webhook')
        topic = kwargs.get('topic')
        name = kwargs.get('name').upper()
        chat_id = update.message.chat_id

        if self.app.db.get_subscription(chat_id, name):
            text = 'You already subscribed on this updates'
            return self.app.send(bot, update, text=text)

        user = self.app.db.get_user_data(chat_id)
        data = {
            'chat_id': chat_id,
            'user_id': user.get('_id'),
            'webhook_id': webhook.get('_id'),
            'topic': topic,
            'name': name,
        }

        status = self.app.db.create_subscription(data)
        if status:
            text = f'Now you will be notified about updates from {name}'
            return self.app.send(bot, update, text=text)

        text = "We can't subscribe you on updates at this moment"
        self.app.send(bot, update, text=text)


class UnwatchDispatcherCommand(AbstractCommand):
    """
    /unwatch project <name> - Unsubscribe from a selected project updates
    /unwatch issue <name> - Unsubscribe from a selected issue updates
    /unwatch - Unsubscribe from all updates
    """
    targets = ('project', 'issue')
    description = (
        "<b>Command description:</b>\n",
        "/unwatch project <i>project-key</i> - Unsubscribe from a selected project updates\n"
        "/unwatch issue <i>issue-key</i> - Unsubscribe from a selected issue updates\n"
        "/unwatch - Unsubscribe from all updates"
    )

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        parameters_names = ('target', 'name')
        params = dict(zip_longest(parameters_names, options))

        if not params['target']:
            confirmation_buttons = [
                InlineKeyboardButton(
                    text='No', callback_data=f'unsubscribe_all:{WatchDispatcherCommand.negative_answer}'
                ),
                InlineKeyboardButton(
                    text='Yes', callback_data=f'unsubscribe_all:{WatchDispatcherCommand.positive_answer}'
                ),
            ]
            buttons = InlineKeyboardMarkup(
                build_menu(confirmation_buttons, n_cols=2)
            )
            text = 'Do you want to unsubscribe from all updates?'
            return self.app.send(bot, update, text=text, buttons=buttons)

        if params['target'] not in self.targets or not params['name']:
            return self.app.send(bot, update, text=self.description)

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
            return self.app.send(bot, update, text='Unsubscribing from all updates was declined')

        user = self.app.db.get_user_data(update.callback_query.message.chat_id)
        status = self.app.db.delete_all_subscription(user.get('_id'))

        if status:
            text = 'You were unsubscribed from all updates'
            return self.app.send(bot, update, text=text)

        text = "Can't unsubscribe you from all updates at this moment, please try again later"
        return self.app.send(bot, update, text=text)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^unsubscribe_all:')


class UnsubscribeOneItemCommand(AbstractCommand):
    """Allows user to unsubscribe from issue or project updates"""

    def handler(self, bot, update, *args, **kwargs):
        topic = kwargs.get('topic')
        name = kwargs.get('name').upper()
        chat_id = update.message.chat_id

        if not self.app.db.get_subscription(chat_id, name):
            text = f'You were not subscribed to {name} {topic.lower()} updates'
            return self.app.send(bot, update, text=text)

        status = self.app.db.delete_subscription(chat_id, name)
        if status:
            text = f'You were unsubscribed from {name} {topic.lower()} updates'
            return self.app.send(bot, update, text=text)

        text = f"Can't unsubscribe you from {name} {topic.lower()} updates, please try again later"
        return self.app.send(bot, update, text=text)
