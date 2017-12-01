from itertools import zip_longest

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from common import utils

from .base import AbstractCommand, SendMessageFactory


class ContentPaginatorCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        After the user clicked on the page number to be displayed, the handler
        generates a message with the data from the specified page, creates
        a new keyboard and modifies the last message (the one under which
        the key with the page number was pressed)
        """
        scope = self._bot_instance.get_query_scope(update)
        key, page = self.get_issue_data(scope['data'])
        user_data = self._bot_instance.db.get_cached_content(key=key)

        if not user_data:
            text = 'Cache for this content has expired. Repeat the request, please'
            return SendMessageFactory.send(bot, update, text=text, simple_message=True)

        title = user_data['title']
        items = user_data['content'][page - 1]
        page_count = user_data['page_count']
        SendMessageFactory.send(bot, update, title=title, items=items, page=page, page_count=page_count, key=key)

    def get_issue_data(self, query_data):
        """
        Gets key and page for cached issues
        :param query_data: 'paginator:IHB#13'
        :return: ('IHB', 13)
        """
        data = query_data.replace('paginator:', '')
        key, page = data.split('#')

        return key, int(page)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^paginator:')


class ListUnresolvedIssuesCommand(AbstractCommand):
    """
    /listunresolved <target> [name] - shows users or projects unresolved issues
    """
    targets = ('my', 'user', 'project')

    @utils.login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        parameters_names = ('target', 'name')
        description = "<b>Command description:</b>\n" \
                      "/listunresolved my - returns a list of user's unresolved issues\n" \
                      "/listunresolved user <i>username</i> - returns a list of selected user issues\n" \
                      "/listunresolved project <i>KEY</i> - returns a list of projects issues\n"

        params = dict(zip_longest(parameters_names, options))
        optional_condition = params['target'] != 'my' and not params['name']

        if not params['target'] or params['target'] not in self.targets or optional_condition:
            return SendMessageFactory.send(bot, update, text=description, simple_message=True)

        if params['target'] == 'my':
            return UserUnresolvedCommand(self._bot_instance).handler(
                bot, update, username=auth_data.username, *args, **kwargs
            )
        elif params['target'] == 'user':
            return UserUnresolvedCommand(self._bot_instance).handler(
                bot, update, username=params['name'], *args, **kwargs
            )
        elif params['target'] == 'project':
            ProjectUnresolvedCommand(self._bot_instance).handler(bot, update, project=params['name'], *args, **kwargs)

    def command_callback(self):
        return CommandHandler('listunresolved', self.handler, pass_args=True)


class UserUnresolvedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Shows user's unresolved issues"""
        telegram_id = update.message.chat_id
        auth_data = kwargs.get('auth_data')
        username = kwargs.get('username')

        # check if the user exists on Jira host
        self._bot_instance.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)

        title = 'All unresolved tasks of {}:'.format(username)
        raw_items = self._bot_instance.jira.get_open_issues(username=username, auth_data=auth_data)
        key = '{}:{}'.format(telegram_id, username)
        SendMessageFactory.send(bot, update, title=title, raw_items=raw_items, key=key)


class ProjectUnresolvedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Shows project unresolved issues"""
        telegram_id = update.message.chat_id
        auth_data = kwargs.get('auth_data')
        project = kwargs.get('project')

        # check if the project exists on Jira host
        self._bot_instance.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)

        title = 'Unresolved tasks of project {}:'.format(project)
        raw_items = self._bot_instance.jira.get_open_project_issues(project=project, auth_data=auth_data)
        key = '{}:{}'.format(telegram_id, project)
        SendMessageFactory.send(bot, update, title=title, raw_items=raw_items, key=key)


class ListStatusIssuesCommand(AbstractCommand):
    """
    /liststatus <target> [name] - shows users or projects issues by a selected status
    """
    targets = ('my', 'user', 'project')

    @utils.login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        parameters_names = ('target', 'name')
        description = "<b>Command description:</b>\n" \
                      "/liststatus my - returns a list of user's issues with a selected status\n" \
                      "/liststatus user *username* - returns a list of selected user issues and status\n" \
                      "/liststatus project *KEY* - returns a list of projects issues with selected status\n"

        params = dict(zip_longest(parameters_names, options))
        optional_condition = params['target'] != 'my' and not params['name']

        if not params['target'] or params['target'] not in self.targets or optional_condition:
            return SendMessageFactory.send(bot, update, text=description, simple_message=True)

        if params['target'] == 'my':
            return UserStatusIssuesMenu(self._bot_instance).handler(
                bot, update, username=auth_data.username, *args, **kwargs
            )
        elif params['target'] == 'user':
            return UserStatusIssuesMenu(self._bot_instance).handler(
                bot, update, username=params['name'], *args, **kwargs
            )
        elif params['target'] == 'project':
            ProjectStatusIssuesMenu(self._bot_instance).handler(bot, update, project=params['name'], *args, **kwargs)

    def command_callback(self):
        return CommandHandler('liststatus', self.handler, pass_args=True)


class UserStatusIssuesMenu(AbstractCommand):
    """
    Shows an inline keyboard with only those statuses that are in user's issues
    """
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        username = kwargs.get('username')
        button_list = list()
        text = 'Pick up one of the statuses:'
        reply_markup = None

        # check if the user exists on Jira host
        self._bot_instance.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)

        # getting statuses from user's unresolved issues
        raw_items = self._bot_instance.jira.get_open_issues(username=username, auth_data=auth_data)
        statuses = {issue.fields.status.name for issue in raw_items}

        # creating an inline keyboard for showing buttons
        if statuses:
            for status in sorted(statuses):
                button_list.append(
                    InlineKeyboardButton(status, callback_data='user_status:{}:{}'.format(username, status))
                )
            reply_markup = InlineKeyboardMarkup(utils.build_menu(button_list, n_cols=2))
        else:
            text = 'You do not have assigned issues'

        SendMessageFactory.send(bot, update, text=text, buttons=reply_markup, simple_message=True)


class ProjectStatusIssuesMenu(AbstractCommand):
    """
    Shows an inline keyboard with only those statuses that are in projects issues
    """
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        project = kwargs.get('project')
        button_list = list()
        text = 'Pick up one of the statuses:'
        reply_markup = None

        # check if the project exists on Jira host
        self._bot_instance.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)

        # getting statuses from projects unresolved issues
        raw_items = self._bot_instance.jira.get_open_project_issues(project=project, auth_data=auth_data)
        statuses = {issue.fields.status.name for issue in raw_items}

        # creating an inline keyboard for showing buttons
        if statuses:
            for status in sorted(statuses):
                button_list.append(
                    InlineKeyboardButton(status, callback_data='project_status:{}:{}'.format(project, status))
                )
            reply_markup = InlineKeyboardMarkup(utils.build_menu(button_list, n_cols=2))
        else:
            text = 'The project "{}" has no issues'.format(project)

        SendMessageFactory.send(bot, update, text=text, buttons=reply_markup, simple_message=True)


class UserStatusIssuesCommand(AbstractCommand):
    """
    Shows a user's issues with selected status
    NOTE: Available only after user selected a status at inline keyboard
    """
    @utils.login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        scope = self._bot_instance.get_query_scope(update)
        username, status = scope['data'].replace('user_status:', '').split(':')

        title = 'Issues of "{}" with the "{}" status'.format(username, status)
        raw_items = self._bot_instance.jira.get_user_status_issues(username, status, auth_data=auth_data)
        key = 'us_issue:{}:{}:{}'.format(scope['telegram_id'], username, status)  # user_status
        SendMessageFactory.send(bot, update, title=title, raw_items=raw_items, key=key)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^user_status:')


class ProjectStatusIssuesCommand(AbstractCommand):
    """
    Shows a project issues with selected status
    NOTE: Available only after user selected a status at inline keyboard
    """
    @utils.login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        scope = self._bot_instance.get_query_scope(update)
        project, status = scope['data'].replace('project_status:', '').split(':')

        title = 'Issues of "{}" project with the "{}" status'.format(project, status)
        raw_items = self._bot_instance.jira.get_project_status_issues(project, status, auth_data=auth_data)
        key = 'ps_issue:{}:{}:{}'.format(scope['telegram_id'], project, status)  # project_status
        SendMessageFactory.send(bot, update, title=title, raw_items=raw_items, key=key)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^project_status:')
