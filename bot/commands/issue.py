from itertools import zip_longest

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot.helpers import login_required, get_query_scope
from bot.exceptions import ContextValidationError
from bot.inlinemenu import build_menu

from .base import AbstractCommand


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
    command_name = "/listunresolved"
    targets = ('my', 'user', 'project')
    description = (
        "<b>Command description:</b>\n"
        "/listunresolved my - returns a list of user's unresolved issues\n"
        "/listunresolved user <i>username</i> - returns a list of selected user issues\n"
        "/listunresolved project <i>KEY</i> - returns a list of projects issues\n"
    )

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')
        parameters_names = ('target', 'name')
        params = dict(zip_longest(parameters_names, options))
        optional_condition = params['target'] != 'my' and not params['name']

        if not params['target'] or params['target'] not in self.targets or optional_condition:
            return self.app.send(bot, update, text=self.description)

        if params['target'] == 'my':
            return UserUnresolvedCommand(self.app).handler(
                bot, update, username=auth_data.username, *args, **kwargs
            )
        elif params['target'] == 'user':
            return UserUnresolvedCommand(self.app).handler(
                bot, update, username=params['name'], *args, **kwargs
            )
        elif params['target'] == 'project':
            ProjectUnresolvedCommand(self.app).handler(bot, update, project=params['name'], *args, **kwargs)

    def command_callback(self):
        return CommandHandler('listunresolved', self.handler, pass_args=True)

    @classmethod
    def check_command(cls, command_name):
        # validate command name
        return command_name == cls.command_name

    @classmethod
    def validate_context(cls, context):
        if len(context) < 1:
            raise ContextValidationError(cls.description)

        target = context.pop(0)
        # validate command options
        if target == 'my':
            if len(context) > 1:
                raise ContextValidationError("<i>my</i> not accept any arguments.")
        elif target == 'user':
            if len(context) < 1:
                raise ContextValidationError("<i>USERNAME</i> is a required argument.")
        elif target == 'project':
            if len(context) < 1:
                raise ContextValidationError("<i>KEY</i> is a required argument.")
        else:
            raise ContextValidationError(f"Argument {target} not allowed.")


class UserUnresolvedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Shows user's unresolved issues"""
        telegram_id = update.message.chat_id
        auth_data = kwargs.get('auth_data')
        username = kwargs.get('username')

        # check if the user exists on Jira host
        self.app.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)

        title = 'All unresolved tasks of {}:'.format(username)
        raw_items = self.app.jira.get_open_issues(username=username, auth_data=auth_data)
        key = '{}:{}'.format(telegram_id, username)
        self.app.send(bot, update, title=title, raw_items=raw_items, key=key)


class ProjectUnresolvedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Shows project unresolved issues"""
        telegram_id = update.message.chat_id
        auth_data = kwargs.get('auth_data')
        project = kwargs.get('project')

        # check if the project exists on Jira host
        self.app.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)

        title = 'Unresolved tasks of project {}:'.format(project)
        raw_items = self.app.jira.get_open_project_issues(project=project, auth_data=auth_data)
        key = '{}:{}'.format(telegram_id, project)
        self.app.send(bot, update, title=title, raw_items=raw_items, key=key)


class ListStatusIssuesCommand(AbstractCommand):
    """
    /liststatus <target> [name] [status] - shows users or projects issues by a selected status
    """
    command_name = "/liststatus"
    targets = ('user', 'project')
    description = (
        "<b>Command description:</b>\n"
        "/liststatus user <i>username</i> <i>status</i> - returns a list of selected "
        "user issues and status (status is optional)\n"
        "/liststatus project <i>key</i> <i>status</i> - returns a list of projects "
        "issues with selected status (status is optional)\n"
    )

    @login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        parameters_names = ('target', 'name', 'status')
        options = kwargs.get('args')

        if not options:
            return self.app.send(bot, update, text=self.description)

        # because `options` comes as a split string in a list
        # it is necessary to combine the status in a single line
        try:
            target, name, *splited_status = options
        except ValueError:
            return self.app.send(bot, update, text=self.description)
        options = [target, name, ' '.join(splited_status)]
        params = dict(zip_longest(parameters_names, options))

        if params.get('target') not in self.targets:
            return self.app.send(bot, update, text=self.description)

        if params['status']:
            self.app.jira.is_status_exists(host=auth_data.jira_host, status=params['status'], auth_data=auth_data)

            if params['target'] == 'user':
                kwargs.update({'username': params['name'], 'status': params['status']})
                return UserStatusIssuesCommand(self.app).handler(bot, update, *args, **kwargs)
            elif params['target'] == 'project':
                kwargs.update({'project': params['name'], 'status': params['status']})
                return ProjectStatusIssuesCommand(self.app).handler(bot, update, *args, **kwargs)

        if params['target'] == 'user':
            return UserStatusIssuesMenu(self.app).handler(
                bot, update, username=params['name'], *args, **kwargs
            )
        elif params['target'] == 'project':
            ProjectStatusIssuesMenu(self.app).handler(bot, update, project=params['name'], *args, **kwargs)

    def command_callback(self):
        return CommandHandler('liststatus', self.handler, pass_args=True)

    @classmethod
    def check_command(cls, command_name):
        # validate command name
        return command_name == cls.command_name

    @classmethod
    def validate_context(cls, context):
        if len(context) < 1:
            raise ContextValidationError(cls.description)

        target = context.pop(0)
        # validate command options
        if target == 'user':
            if len(context) < 1:
                raise ContextValidationError("<i>USERNAME</i> is a required argument.")
        elif target == 'project':
            if len(context) < 1:
                raise ContextValidationError("<i>KEY</i> is a required argument.")
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

        # check if the user exists on Jira host
        self.app.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)

        # getting statuses from user's unresolved issues
        raw_items = self.app.jira.get_open_issues(username=username, auth_data=auth_data)
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

        # check if the project exists on Jira host
        self.app.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)

        # getting statuses from projects unresolved issues
        raw_items = self.app.jira.get_open_project_issues(project=project, auth_data=auth_data)
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
