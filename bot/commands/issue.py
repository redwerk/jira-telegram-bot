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
    targets = ('my', 'user', 'project')

    @utils.login_required
    def handler(self, bot, update, *args, **kwargs):
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')

        if not options or options[0] not in self.targets:
            text = "<b>Command description:</b>\n" \
                   "/listunresolved my - returns a list of user's unresolved issues\n" \
                   "/listunresolved user <i>username</i> - returns a list of selected user issues\n" \
                   "/listunresolved project <i>KEY</i> - returns a list of projects issues\n"
            return SendMessageFactory.send(bot, update, text=text, simple_message=True)

        target = options[0]
        try:
            name = options[1]
        except IndexError:
            if target != 'my':
                # name option is required for `user` and `project` targets
                text = 'Second argument is required for this type of command'
                return SendMessageFactory.send(bot, update, text=text, simple_message=True)
            else:
                # name option not needed for `my` target
                return UserUnresolvedCommand(self._bot_instance).handler(
                    bot, update, username=auth_data.username, *args, **kwargs
                )
        else:
            if target == 'user' and name:
                return UserUnresolvedCommand(self._bot_instance).handler(bot, update, username=name, *args, **kwargs)
            elif target == 'project' and name:
                ProjectUnresolvedCommand(self._bot_instance).handler(bot, update, project=name, *args, **kwargs)

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
