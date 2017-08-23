from telegram import ParseMode
from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory
from .menu import ChooseProjectMenuCommand, ChooseStatusMenuCommand


class UserUnresolvedIssuesCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Receiving open user issues and modifying the current message
        :return: Message with a list of open user issues
        """
        issues, status = self._bot_instance.jira.get_open_issues(**credentials)
        self.show_title(bot, '<b>All your unresolved tasks:</b>', scope['chat_id'], scope['message_id'])

        if not issues:
            self.show_content(bot, 'Woohoo! You have no unresolved tasks', scope['chat_id'])
            return

        key = '{}:{}'.format(scope['telegram_id'], credentials.get('username'))
        formatted_issues, buttons = self._bot_instance.save_into_cache(data=issues, key=key)
        self.show_content(bot, formatted_issues, scope['chat_id'], buttons)

    @staticmethod
    def show_title(bot, title, chat_id, message_id):
        """
        Shows title of the request in chat with a user
        It is possible to display data in HTML mode
        """
        bot.edit_message_text(
            text=title,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )

    @staticmethod
    def show_content(bot, content, chat_id, buttons=None):
        """
        Shows a requested data in chat with a user
        It is possible to display data in HTML mode
        """
        bot.send_message(
            text=content,
            chat_id=chat_id,
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )


class ProjectUnresolvedIssuesCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Call order: /menu > Issues > Open project issues > Some project
        Shows unresolved issues by selected project
        """
        project = kwargs.get('project')

        issues, status_code = self._bot_instance.jira.get_open_project_issues(project=project, **credentials)

        UserUnresolvedIssuesCommand.show_title(
            bot,
            '<b>Unresolved tasks of project {}:</b>'.format(project),
            scope['chat_id'],
            scope['message_id'])

        if not issues:
            UserUnresolvedIssuesCommand.show_content(
                bot,
                "Project <b>{}</b> doesn't have any unresolved tasks".format(project),
                scope['chat_id']
            )
            return

        key = '{}:{}'.format(scope['telegram_id'], project)
        formatted_issues, buttons = self._bot_instance.save_into_cache(data=issues, key=key)
        UserUnresolvedIssuesCommand.show_content(bot, formatted_issues, scope['chat_id'], buttons)


class ProjectStatusIssuesCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Call order: /menu > Issues > Open project issues >
                    > Some project  > Some status
        Shows project issues with selected status
        """
        project = kwargs.get('project')
        status = kwargs.get('status')
        project_key = '{}:{}:{}'.format(scope['telegram_id'], project, status)

        issues, status_code = self._bot_instance.jira.get_project_status_issues(
            project=project, status=status, **credentials
        )

        UserUnresolvedIssuesCommand.show_title(
            bot,
            'All tasks with <b>«{}»</b> status in <b>{}</b> project:'.format(status, project),
            scope['chat_id'],
            scope['message_id'])

        if not issues:
            message = "No tasks with <b>«{}»</b> status in <b>{}</b> project ".format(status, project)
            UserUnresolvedIssuesCommand.show_content(bot, message, scope['chat_id'])
            return

        formatted_issues, buttons = self._bot_instance.save_into_cache(data=issues, key=project_key)
        UserUnresolvedIssuesCommand.show_content(bot, formatted_issues, scope['chat_id'], buttons)


class ContentPaginatorCommand(AbstractCommand):

    def handler(self, bot, scope, user_data, *args, **kwargs):
        """
        After the user clicked on the page number to be displayed, the handler
        generates a message with the data from the specified page, creates
        a new keyboard and modifies the last message (the one under which
        the key with the page number was pressed)
        """
        key = kwargs.get('key')
        page = kwargs.get('page')
        str_key = 'paginator:{}'.format(key)

        buttons = utils.get_pagination_keyboard(
            current=page,
            max_page=user_data['page_count'],
            str_key=str_key + '#{}'
        )
        formatted_issues = '\n\n'.join(user_data['content'][page - 1])

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )


class IssueCommandFactory(AbstractCommandFactory):

    commands = {
        "issues:my": UserUnresolvedIssuesCommand,
        "issues:p": ChooseProjectMenuCommand,
        "issues:ps": ChooseProjectMenuCommand
    }

    patterns = {
        "issues:my": 'ignore',
        "issues:p": 'project:{}',
        "issues:ps": 'project_s_menu:{}'
    }

    def command(self, bot, update, *args, **kwargs):
        """
        Call order: /menu > Issues > Any option
        """
        scope = self._bot_instance.get_query_scope(update)
        credentials, message = self._bot_instance.get_and_check_cred(scope['telegram_id'])

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        obj = self._command_factory_method(scope['data'])
        obj.handler(bot, scope, credentials, pattern=self.patterns[scope['data']], footer='issues_menu')

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^issues:')


class ProjectIssuesFactory(AbstractCommandFactory):
    commands = {
        'project': ProjectUnresolvedIssuesCommand,
        'project_s': ProjectStatusIssuesCommand,
        'project_s_menu': ChooseStatusMenuCommand
    }

    def command(self, bot, update, *args, **kwargs):
        """
        Call order: /menu > Issues > Any option
        """
        scope = self._bot_instance.get_query_scope(update)
        cmd, project, *status = scope['data'].split(':')
        if status:
            status = status[0]

        obj = self._command_factory_method(cmd)

        credentials, message = self._bot_instance.get_and_check_cred(
            scope['telegram_id']
        )

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        _pattern = 'project_s:' + project + ':{}'
        obj.handler(bot, scope, credentials, project=project, status=status, pattern=_pattern, footer='issues:ps')

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^project')


class ContentPaginatorFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        scope = self._bot_instance.get_query_scope(update)
        key, page = self._bot_instance.get_issue_data(scope['data'])
        user_data = self._bot_instance.db.get_cached_content(key=key)

        if not user_data:
            bot.edit_message_text(
                text='Cache for this content has expired. Repeat the request, please',
                chat_id=scope['chat_id'],
                message_id=scope['message_id'],
            )
            return

        ContentPaginatorCommand(self._bot_instance).handler(bot, scope, user_data, key=key, page=page)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^paginator:')
