from telegram import ChatAction, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from .base import AbstractCommand, AbstractCommandFactory

from bot import utils


class UserUnresolvedIssuesCommand(AbstractCommand):

    def handler(self, bot, telegram_id, chat_id, message_id):
        """
        Receiving open user issues and modifying the current message
        :param bot:
        :param telegram_id: user id
        :param chat_id: chat id with user
        :param message_id: last message id
        :return: Message with a list of open user issues
        """
        bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        credentials, message = self._bot_instance.__get_and_check_cred(telegram_id)

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=chat_id,
                message_id=message_id
            )
            return

        username = credentials.get('username')
        password = credentials.get('password')

        issues, status = self._bot_instance.__jira.get_open_issues(
            username=username, password=password
        )

        if not issues:
            bot.edit_message_text(
                text='You have no unresolved issues',
                chat_id=chat_id,
                message_id=message_id
            )
            return

        buttons = None
        if len(issues) < self._bot_instance.issues_per_page:
            formatted_issues = '\n\n'.join(issues)
        else:
            user_issues = utils.split_by_pages(issues, self._bot_instance.issues_per_page)
            page_count = len(user_issues)
            self._bot_instance.__issue_cache[username] = dict(
                issues=user_issues, page_count=page_count
            )

            # return the first page
            formatted_issues = '\n\n'.join(user_issues[0])
            str_key = 'paginator:{}'.format(username)
            buttons = utils.get_pagination_keyboard(
                current=1,
                max_page=page_count,
                str_key=str_key + '-{}'
            )

        bot.edit_message_text(
            text=formatted_issues,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=buttons
        )


class ChooseProjectCommand(AbstractCommand):

    def handler(self, bot, telegram_id, chat_id, message_id, status=False):
        """
        Call order: /menu > Issues > Unresolved by project
        Displaying inline keyboard with names of projects

        :param bot:
        :param telegram_id: user id in telegram
        :param chat_id: current chat whith a user
        :param message_id: last message
        """
        credentials, message = self._bot_instance.__get_and_check_cred(telegram_id)

        if not credentials:
            bot.edit_message_text(
                text=message,
                chat_id=chat_id,
                message_id=message_id
            )
            return

        username = credentials.get('username')
        password = credentials.get('password')

        projects_buttons = list()
        projects, status_code = self._bot_instance.__jira.get_projects(
            username=username, password=password
        )

        if not projects:
            bot.edit_message_text(
                text="Sorry, can't get projects",
                chat_id=chat_id,
                message_id=message_id
            )
            return

        if status:
            _callback = 'project_s_menu:{}'
        else:
            _callback = 'project:{}'

        # dynamic keyboard creation
        for project_name in projects:
            projects_buttons.append(
                InlineKeyboardButton(
                    text=project_name,
                    callback_data=_callback.format(project_name)
                )
            )

        footer_button = [
            InlineKeyboardButton('« Back', callback_data='issues_menu')
        ]
        buttons = InlineKeyboardMarkup(
            utils.build_menu(
                projects_buttons,
                n_cols=3,
                footer_buttons=footer_button)
        )

        bot.edit_message_text(
            text='Choose one of the projects',
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=buttons
        )


class ChooseProjectMenuCommand(ChooseProjectCommand):

    def handler(self, bot, telegram_id, chat_id, message_id, status=True):
        super(self, ChooseProjectMenuCommand).handler(bot, telegram_id, chat_id, message_id, status=status)


class IssueCommandFactory(AbstractCommandFactory):

    commands = {
        "issues:my": UserUnresolvedIssuesCommand,
        "issues:p": ChooseProjectCommand,
        "issues:ps": ChooseProjectMenuCommand
    }

    def command(self, bot, update, *args, **kwargs):
        """
        Call order: /menu > Issues > Any option
        """
        scope = self._bot_instance.__get_query_scope(update)
        obj = self._command_factory_method(scope['data'])
        obj.handler(bot, scope['telegram_id'], scope['chat_id'], scope['message_id'])

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'^issues:')
