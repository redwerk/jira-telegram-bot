import logging

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

        if not issues:
            bot.edit_message_text(
                text='You have no unresolved tasks',
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        formatted_issues, buttons = self._bot_instance.save_into_cache(issues, credentials.get('username'))

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
        )


class ProjectUnresolvedIssuesCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Call order: /menu > Issues > Open project issues > Some project
        Shows unresolved issues by selected project
        """
        project = kwargs.get('project')

        issues, status_code = self._bot_instance.jira.get_open_project_issues(project=project, **credentials)

        if not issues:
            bot.edit_message_text(
                text="Project doesn't have any unresolved tasks",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        formatted_issues, buttons = self._bot_instance.save_into_cache(issues, project)

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
        )


class ProjectStatusIssuesCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Call order: /menu > Issues > Open project issues >
                    > Some project  > Some status
        Shows project issues with selected status
        """
        buttons = None
        project = kwargs.get('project')
        status = kwargs.get('status')
        project_key = '{}:{}'.format(project, status)

        issues, status_code = self._bot_instance.jira.get_project_status_issues(
            project=project, status=status, **credentials
        )

        if not issues:
            bot.edit_message_text(
                text="Project {} doesn't have any "
                     "tasks with {} status".format(project, status),
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        formatted_issues, buttons = self._bot_instance.save_into_cache(issues, project_key)

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
        )


class IssuesPaginatorCommand(AbstractCommand):

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
        formatted_issues = '\n\n'.join(user_data['issues'][page - 1])

        if page == user_data.get('page_count'):
            formatted_issues += user_data.get('footer')

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


class IssuesPaginatorFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        scope = self._bot_instance.get_query_scope(update)
        key, page = self._bot_instance.get_issue_data(scope['data'])
        user_data = self._bot_instance.issue_cache.get(key)

        if not user_data:
            logging.info('There is no data in the cache for {}'.format(key))
            return

        IssuesPaginatorCommand(self._bot_instance).handler(
            bot, scope, user_data,
            key=key, page=page
        )

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^paginator:')
