import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot.exceptions import ContextValidationError
from bot.helpers import get_query_scope, login_required
from bot.inlinemenu import build_menu
from bot.schedules import schedule_commands
from lib.utils import read_file

from .base import AbstractCommand, CommandArgumentParser


class ContentPaginatorCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        After the user clicked on the page number to be displayed, the handler
        generates a message with the data from the specified page, creates
        a new keyboard and modifies the last message (the one under which
        the key with the page number was pressed)
        """
        scope = get_query_scope(update)
        key, page = self.get_issue_data(scope['data'])
        user_data = self.app.db.get_cached_content(key=key)

        if not user_data:
            text = 'Cache for this content has expired. Repeat the request, please'
            return self.app.send(bot, update, text=text)

        title = user_data['title']
        items = user_data['content'][page - 1]
        page_count = user_data['page_count']
        self.app.send(bot, update, title=title, items=items, page=page, page_count=page_count, key=key)

    @staticmethod
    def get_issue_data(query_data):
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
    description = read_file(os.path.join('bot', 'templates', 'listunresolved_description.tpl'))

    @staticmethod
    def get_argparsers():
        my = CommandArgumentParser(prog='my', add_help=False)
        my.add_argument('target', type=str, choices=['my'], nargs='?')

        user = CommandArgumentParser(prog="user", add_help=False)
        user.add_argument('target', type=str, choices=['user'], )
        user.add_argument('username', type=str)

        project = CommandArgumentParser(prog="project", add_help=False)
        project.add_argument('target', type=str, choices=['project'])
        project.add_argument('project_key', type=str)

        return [my, user, project]

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        arguments = kwargs.get('args')
        options = self.resolve_arguments(arguments, auth_data, False)

        if options.target == 'my':
            return UserUnresolvedCommand(self.app).handler(
                bot, update, username=auth_data.username, *args, **kwargs
            )
        elif options.target == 'user' and options.username:
            return UserUnresolvedCommand(self.app).handler(
                bot, update, username=options.username, *args, **kwargs
            )
        elif options.target == 'project' and options.project_key:
            ProjectUnresolvedCommand(self.app).handler(bot, update, project=options.project_key, *args, **kwargs)

    def _check_jira(self, options, auth_data):
        if options.target == 'my':
            self.app.jira.is_user_on_host(username=auth_data.username, auth_data=auth_data)
        elif options.target == 'user':
            self.app.jira.is_user_on_host(username=options.username, auth_data=auth_data)
        elif options.target == 'project':
            self.app.jira.is_project_exists(project=options.project_key, auth_data=auth_data)
        else:
            pass

    def command_callback(self):
        return CommandHandler('listunresolved', self.handler, pass_args=True)

    def validate_context(self, context):
        if not context:
            raise ContextValidationError(self.description)

        target = context.pop(0)
        # validate command options
        if target == 'my':
            if context:
                raise ContextValidationError("<i>my</i> doesn't accept any arguments.")
        elif target == 'user':
            raise ContextValidationError("<i>USERNAME</i> is a required argument.")
        elif target == 'project':
            raise ContextValidationError("<i>KEY</i> is a required argument.")
        else:
            raise ContextValidationError(f"Argument {target} not allowed.")


class UserUnresolvedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Shows user's unresolved issues"""
        telegram_id = update.message.chat_id
        auth_data = kwargs.get('auth_data')
        username = kwargs.get('username')

        title = 'All unresolved tasks of {}:'.format(username)
        raw_items = self.app.jira.get_issues(username=username, resolution='Unresolved', auth_data=auth_data)
        key = '{}:{}'.format(telegram_id, username)
        self.app.send(bot, update, title=title, raw_items=raw_items, key=key)


class ProjectUnresolvedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Shows project unresolved issues"""
        telegram_id = update.message.chat_id
        auth_data = kwargs.get('auth_data')
        project = kwargs.get('project')

        # check if the project exists on Jira host
        self.app.jira.is_project_exists(project=project, auth_data=auth_data)

        title = 'Unresolved tasks of project {}:'.format(project)
        raw_items = self.app.jira.get_project_issues(project=project, resolution='Unresolved', auth_data=auth_data)
        key = '{}:{}'.format(telegram_id, project)
        self.app.send(bot, update, title=title, raw_items=raw_items, key=key)


class ListStatusIssuesCommand(AbstractCommand):
    """
    /liststatus <target> [name] - shows users or projects issues by a selected status
    """
    description = read_file(os.path.join('bot', 'templates', 'liststatus_description.tpl'))

    @staticmethod
    def get_argparsers():
        my = CommandArgumentParser(prog="my", add_help=False)
        my.add_argument('target', type=str, choices=['my'], nargs='?')
        my.add_argument('status', type=str, nargs="?")

        user = CommandArgumentParser(prog="user", add_help=False)
        user.add_argument('target', type=str, choices=['user'], nargs='?')
        user.add_argument('username', type=str)
        user.add_argument('status', type=str, nargs="?")

        project = CommandArgumentParser(prog="project", add_help=False)
        project.add_argument('target', type=str, choices=['project'], nargs='?')
        project.add_argument('project_key', type=str)
        project.add_argument('status', type=str, nargs="?")

        return [my, user, project]

    def _check_jira(self, options, auth_data):
        if options.status:
            self.app.jira.is_status_exists(status=options.status, auth_data=auth_data)
        if options.target == 'my':
            pass
        elif options.target == 'user':
            self.app.jira.is_user_on_host(username=options.username, auth_data=auth_data)
        elif options.target == 'project':
            self.app.jira.is_project_exists(project=options.project_key, auth_data=auth_data)

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        arguments = kwargs.get('args')
        options = self.resolve_arguments(arguments, auth_data)

        if options.target == 'my':
            if options.status:
                kwargs.update({'username': auth_data.username, 'status': options.status})
                UserStatusIssuesCommand(self.app).handler(bot, update, *args, **kwargs)
            else:
                UserStatusIssuesMenu(self.app).handler(bot, update, username=auth_data.username, *args, **kwargs)
        elif options.target == 'user' and options.username:
            if options.status:
                kwargs.update({'username': options.username, 'status': options.status})
                UserStatusIssuesCommand(self.app).handler(bot, update, *args, **kwargs)
            else:
                UserStatusIssuesMenu(self.app).handler(bot, update, username=options.username, *args, **kwargs)
        elif options.target == 'project' and options.project:
            if options.status:
                kwargs.update({'project': options.project, 'status': options.status})
                ProjectStatusIssuesCommand(self.app).handler(bot, update, *args, **kwargs)
            else:
                ProjectStatusIssuesMenu(self.app).handler(bot, update, project=options.project_key, *args, **kwargs)

    def command_callback(self):
        return CommandHandler('liststatus', self.handler, pass_args=True)

    def validate_context(self, context):
        if not context:
            raise ContextValidationError(self.description)

        target = context.pop(0)
        if target == 'my':
            raise ContextValidationError("<i>{status}</i> is a required argument.")
        elif target == 'user':
            raise ContextValidationError("<i>{username}</i> and <i>{status}</i> are required arguments.")
        elif target == 'project':
            raise ContextValidationError("<i>{project_key}</i> and <i>{status}</i> are required arguments.")
        else:
            raise ContextValidationError(f"Argument {target} not allowed.")


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

        # getting statuses from user's unresolved issues
        raw_items = self.app.jira.get_issues(username=username, auth_data=auth_data)
        statuses = {issue.fields.status.name for issue in raw_items}

        # creating an inline keyboard for showing buttons
        if statuses:
            for status in sorted(statuses):
                button_list.append(
                    InlineKeyboardButton(status, callback_data='user_status:{}:{}'.format(username, status))
                )
            reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2))
        else:
            text = 'You do not have assigned issues'

        self.app.send(bot, update, text=text, buttons=reply_markup)


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

        # getting statuses from projects unresolved issues
        raw_items = self.app.jira.get_project_issues(project=project, auth_data=auth_data)
        statuses = {issue.fields.status.name for issue in raw_items}

        # creating an inline keyboard for showing buttons
        if statuses:
            for status in sorted(statuses):
                button_list.append(
                    InlineKeyboardButton(status, callback_data='project_status:{}:{}'.format(project, status))
                )
            reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2))
        else:
            text = 'The project "{}" has no issues'.format(project)

        self.app.send(bot, update, text=text, buttons=reply_markup)


class UserStatusIssuesCommand(AbstractCommand):
    """
    Shows a user's issues with selected status
    NOTE: Available only after user selected a status at inline keyboard
    """
    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        try:
            scope = get_query_scope(update)
        except AttributeError:
            telegram_id = update.message.chat_id
            username = kwargs.get('username')
            status = kwargs.get('status')
        else:
            telegram_id = scope['telegram_id']
            username, status = scope['data'].replace('user_status:', '').split(':')

        title = 'Issues of "{}" with the "{}" status'.format(username, status)
        raw_items = self.app.jira.get_user_status_issues(username, status, auth_data=auth_data)
        key = 'us_issue:{}:{}:{}'.format(telegram_id, username, status)  # user_status
        self.app.send(bot, update, title=title, raw_items=raw_items, key=key)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^user_status:')


class ProjectStatusIssuesCommand(AbstractCommand):
    """
    Shows a project issues with selected status
    NOTE: Available only after user selected a status at inline keyboard
    """
    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        try:
            scope = get_query_scope(update)
        except AttributeError:
            telegram_id = update.message.chat_id
            project = kwargs.get('project')
            status = kwargs.get('status')
        else:
            telegram_id = scope['telegram_id']
            project, status = scope['data'].replace('project_status:', '').split(':')

        title = 'Issues of "{}" project with the "{}" status'.format(project, status)
        raw_items = self.app.jira.get_project_status_issues(project, status, auth_data=auth_data)
        key = 'ps_issue:{}:{}:{}'.format(telegram_id, project, status)  # project_status
        self.app.send(bot, update, title=title, raw_items=raw_items, key=key)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^project_status:')


schedule_commands.register('listunresolved', ListUnresolvedIssuesCommand)
schedule_commands.register('liststatus', ListStatusIssuesCommand)
