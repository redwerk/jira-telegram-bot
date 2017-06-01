import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class UserUnresolvedIssuesCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Receiving open user issues and modifying the current message
        :return: Message with a list of open user issues
        """
        issues, status = self._bot_instance.jira.get_open_issues(
            username=credentials.get('username'), password=credentials.get('password')
        )

        if not issues:
            bot.edit_message_text(
                text='You have no unresolved issues',
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        buttons = None
        if len(issues) < self._bot_instance.issues_per_page:
            formatted_issues = '\n\n'.join(issues)
        else:
            user_issues = utils.split_by_pages(issues, self._bot_instance.issues_per_page)
            page_count = len(user_issues)
            self._bot_instance.issue_cache[credentials.get('username')] = dict(
                issues=user_issues, page_count=page_count
            )

            # return the first page
            formatted_issues = '\n\n'.join(user_issues[0])
            str_key = 'paginator:{}'.format(credentials.get('username'))
            buttons = utils.get_pagination_keyboard(
                current=1,
                max_page=page_count,
                str_key=str_key + '-{}'
            )

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
        )


class ChooseProjectMenuCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Call order: /menu > Issues > Unresolved by project
        Displaying inline keyboard with names of projects
        """
        _callback = kwargs.get('pattern')
        _footer = kwargs.get('footer')

        projects_buttons = list()
        projects, status_code = self._bot_instance.jira.get_projects(
            username=credentials.get('username'), password=credentials.get('password')
        )

        if not projects:
            bot.edit_message_text(
                text="Sorry, can't get projects",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        # dynamic keyboard creation
        for project_name in projects:
            projects_buttons.append(
                InlineKeyboardButton(
                    text=project_name,
                    callback_data=_callback.format(project_name)
                )
            )

        footer_button = [
            InlineKeyboardButton('« Back', callback_data=_footer)
        ]
        buttons = InlineKeyboardMarkup(
            utils.build_menu(
                projects_buttons,
                n_cols=3,
                footer_buttons=footer_button)
        )

        bot.edit_message_text(
            text='Choose one of the projects',
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
        buttons = None
        project = kwargs.get('project')

        issues, status_code = self._bot_instance.jira.get_open_project_issues(
            project=project,
            username=credentials.get('username'),
            password=credentials.get('password')
        )

        if not issues:
            bot.edit_message_text(
                text="Project doesn't have any open issues",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        if len(issues) < self._bot_instance.issues_per_page:
            formatted_issues = '\n\n'.join(issues)
        else:
            project_issues = utils.split_by_pages(
                issues,
                self._bot_instance.issues_per_page
            )
            page_count = len(project_issues)
            self._bot_instance.issue_cache[project] = dict(
                issues=project_issues, page_count=page_count
            )
            # return the first page
            formatted_issues = '\n\n'.join(project_issues[0])
            str_key = 'paginator:{name}'.format(name=project)
            buttons = utils.get_pagination_keyboard(
                current=1,
                max_page=page_count,
                str_key=str_key + '-{}'
            )
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
            project=project,
            status=status,
            username=credentials.get('username'),
            password=credentials.get('password')
        )

        if not issues:
            bot.edit_message_text(
                text="Project {} doesn't have any "
                     "issues with {} status".format(project, status),
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        if len(issues) < self._bot_instance.issues_per_page:
            formatted_issues = '\n\n'.join(issues)
        else:
            project_issues = utils.split_by_pages(
                issues, self._bot_instance.issues_per_page
            )
            page_count = len(project_issues)
            self._bot_instance.issue_cache[project_key] = dict(
                issues=project_issues, page_count=page_count
            )
            # return the first page
            formatted_issues = '\n\n'.join(project_issues[0])
            str_key = 'paginator:{name}'.format(name=project_key)
            buttons = utils.get_pagination_keyboard(
                current=1,
                max_page=page_count,
                str_key=str_key + '-{}'
            )

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
        )


class ChooseStatusMenuCommand(AbstractCommand):

    def handler(self, bot, scope, credentials, *args, **kwargs):
        """
        Call order: /menu > Issues > Unresolved by project > Some project
        Displaying inline keyboard with available statuses
        """
        status_buttons = list()
        _callback = kwargs.get('pattern')
        _footer = kwargs.get('footer')
        project = kwargs.get('project')

        statuses, status = self._bot_instance.jira.get_statuses(
            username=credentials['username'],
            password=credentials['password']
        )

        if not statuses:
            bot.edit_message_text(
                text="Sorry, can't get statuses at this moment",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        for _status in statuses:
            status_buttons.append(
                InlineKeyboardButton(
                    text=_status,
                    callback_data=_callback.format(_status)
                )
            )
        footer_button = [
            InlineKeyboardButton('« Back', callback_data=_footer)
        ]

        buttons = InlineKeyboardMarkup(
            utils.build_menu(
                status_buttons,
                n_cols=2,
                footer_buttons=footer_button)
        )
        text = 'You chose {} project.\n' \
               'Choose one of the statuses'.format(project)
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=text,
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
            str_key=str_key + '-{}'
        )
        formatted_issues = '\n\n'.join(user_data['issues'][page - 1])

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            reply_markup=buttons
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
