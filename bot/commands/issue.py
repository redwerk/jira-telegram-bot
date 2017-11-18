from telegram import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from common import utils

from .base import AbstractCommand, AbstractCommandFactory


class ContentPaginatorCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        After the user clicked on the page number to be displayed, the handler
        generates a message with the data from the specified page, creates
        a new keyboard and modifies the last message (the one under which
        the key with the page number was pressed)
        """
        scope = self._bot_instance.get_query_scope(update)
        key, page = self._bot_instance.get_issue_data(scope['data'])
        user_data = self._bot_instance.db.get_cached_content(key=key)
        message_type = self.get_message_type(update)
        result = dict()

        if not user_data:
            result['text'] = 'Cache for this content has expired. Repeat the request, please'
            self.send_factory.send(message_type, bot, update, result, simple_message=True)
            return

        result['title'] = user_data['title']
        result['items'] = user_data['content'][page - 1]
        result['page'] = page
        result['key'] = key
        result['page_count'] = user_data['page_count']
        self.send_factory.send(message_type, bot, update, result, items=True)

    def command_callback(self):
        return CallbackQueryHandler(self.handler, pattern=r'^paginator:')


class ListUnresolvedIssuesCommand(AbstractCommand):
    targets = ('my', 'user', 'project')

    @utils.login_required
    def handler(self, bot, update, *args, **kwargs):
        message_type = self.get_message_type(update)
        result = dict()
        auth_data = kwargs.get('auth_data')
        options = kwargs.get('args')

        if not options or options[0] not in self.targets:
            result['text'] = "<b>Command description:</b>\n" \
                             "/listunresolved my - returns a list of user's unresolved issues\n" \
                             "/listunresolved user <i>username</i> - returns a list of selected user issues\n" \
                             "/listunresolved project <i>KEY</i> - returns a list of projects issues\n"
            self.send_factory.send(message_type, bot, update, result, simple_message=True)
            return

        target = options[0]
        try:
            name = options[1]
        except IndexError:
            if target != 'my':
                # name option is required for `user` and `project` targets
                result['text'] = 'Second argument is required for this type of command'
                return self.send_factory.send(message_type, bot, update, result, simple_message=True)
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
        message_type = self.get_message_type(update)
        result = dict()
        auth_data = kwargs.get('auth_data')
        username = kwargs.get('username')

        # check if the user exists on Jira host
        self._bot_instance.jira.is_user_on_host(host=auth_data.jira_host, username=username, auth_data=auth_data)

        result['title'] = 'All unresolved tasks of {}:'.format(username)
        result['items'] = self._bot_instance.jira.get_open_issues(username=username, auth_data=auth_data)
        result['key'] = '{}:{}'.format(telegram_id, username)
        self.send_factory.send(message_type, bot, update, result, items=True)


class ProjectUnresolvedCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Shows project unresolved issues"""
        telegram_id = update.message.chat_id
        auth_data = kwargs.get('auth_data')
        project = kwargs.get('project')

        # check if the project exists on Jira host
        self._bot_instance.jira.is_project_exists(host=auth_data.jira_host, project=project, auth_data=auth_data)

        # shows title
        bot.send_message(
            text='<b>Unresolved tasks of project {}:</b>'.format(project),
            chat_id=telegram_id,
            parse_mode=ParseMode.HTML
        )

        issues = self._bot_instance.jira.get_open_project_issues(project=project, auth_data=auth_data)
        key = '{}:{}'.format(telegram_id, project)
        formatted_issues, buttons = self._bot_instance.save_into_cache(data=issues, key=key)

        # shows list of issues
        bot.send_message(
            text=formatted_issues,
            chat_id=telegram_id,
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )


class ProjectStatusIssuesCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        Shows project issues with selected status
        Will be used for `/liststatus` command
        """
        auth_data = kwargs.get('auth_data')
        telegram_id = update.message.chat_id
        project = kwargs.get('project')
        status = kwargs.get('status')
        project_key = '{}:{}:{}'.format(telegram_id, project, status)

        # shows title
        bot.send_message(
            text='All tasks with <b>«{}»</b> status in <b>{}</b> project:'.format(status, project),
            chat_id=telegram_id,
            parse_mode=ParseMode.HTML
        )

        issues = self._bot_instance.jira.get_project_status_issues(project=project, status=status, auth_data=auth_data)
        formatted_issues, buttons = self._bot_instance.save_into_cache(data=issues, key=project_key)

        # shows list of issues
        bot.send_message(
            text=formatted_issues,
            chat_id=telegram_id,
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )
