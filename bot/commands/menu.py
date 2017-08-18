from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import utils

from .base import AbstractCommand, AbstractCommandFactory


class MainMenuCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """
        Call order: /menu
        """
        button_list = [
            InlineKeyboardButton(
                'Issues', callback_data='issues_menu'
            ),
            InlineKeyboardButton(
                'Tracking', callback_data='tracking_menu'
            ),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text='What do you want to see?',
            reply_markup=reply_markup
        )


class IssuesMenuCommand(AbstractCommand):

    def handler(self, bot, scope):
        issues_button_list = [
            InlineKeyboardButton('My unresolved', callback_data='issues:my'),
            InlineKeyboardButton('Unresolved by projects', callback_data='issues:p'),
            InlineKeyboardButton('By project with a status', callback_data='issues:ps'),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(issues_button_list, n_cols=2))

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='What tasks do you want to see?',
            reply_markup=reply_markup
        )


class TrackingMenuCommand(AbstractCommand):

    def handler(self, bot, scope):
        tracking_button_list = [
            InlineKeyboardButton('My time', callback_data='tracking-my'),
            InlineKeyboardButton('Project time', callback_data='tracking-p'),
            InlineKeyboardButton('Project time by user', callback_data='tracking-pu')
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(tracking_button_list, n_cols=2))

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='What you want to see?',
            reply_markup=reply_markup
        )


class MainMenuCommandFactory(AbstractCommandFactory):

    def command(self, bot, update, *args, **kwargs):
        telegram_id = update.message.chat_id

        user = self._bot_instance.db.get_user_data(telegram_id)
        access_condition = (
            user.get('access_token'),
            user.get('access_token_secret'),
        )

        if user and all(access_condition):
            MainMenuCommand(self._bot_instance).handler(bot, update, *args, **kwargs)
        else:
            bot.send_message(
                chat_id=telegram_id,
                text='<b>You did not specify credential data. Please, login and try again</b>',
                parse_mode=ParseMode.HTML
            )

    def command_callback(self):
        return CommandHandler('menu', self.command)


class MenuCommandFactory(AbstractCommandFactory):

    commands = {
        "issues_menu": IssuesMenuCommand,
        "tracking_menu": TrackingMenuCommand
    }

    def command(self, bot, update, *args, **kwargs):
        scope = self._bot_instance.get_query_scope(update)
        obj = self._command_factory_method(scope['data'])
        obj.handler(bot, scope)

    def command_callback(self):
        return CallbackQueryHandler(self.command, pattern=r'.+_menu$')


class ChooseDeveloperMenuCommand(AbstractCommand):

    def handler(self, bot, scope: dict, credentials: dict, *args, **kwargs):
        """Displaying inline keyboard with developers names"""

        buttons = list()
        _callback = kwargs.get('pattern')
        _footer = kwargs.get('footer')

        developers, status = self._bot_instance.jira.get_developers(**credentials)

        if not developers:
            bot.edit_message_text(
                text="Sorry, can't get developers at the moment",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        for fullname in sorted(developers):
            buttons.append(
                InlineKeyboardButton(text=fullname, callback_data=_callback.format(fullname))
            )

        footer_button = [
            InlineKeyboardButton('« Back', callback_data=_footer)
        ]

        buttons = InlineKeyboardMarkup(
            utils.build_menu(buttons, n_cols=2, footer_buttons=footer_button)
        )

        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text='Pick a developer',
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
        projects, status_code = self._bot_instance.jira.get_projects(**credentials)

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
                n_cols=4,
                footer_buttons=footer_button)
        )

        bot.edit_message_text(
            text='Pick a project',
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

        statuses, status = self._bot_instance.jira.get_statuses(**credentials)

        if not statuses:
            bot.edit_message_text(
                text="Sorry, can't get statuses at the moment",
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
                n_cols=3,
                footer_buttons=footer_button)
        )
        text = "You've chosen {} project.\n" \
               "Pick a status".format(project)
        bot.edit_message_text(
            chat_id=scope['chat_id'],
            message_id=scope['message_id'],
            text=text,
            reply_markup=buttons
        )


class ChooseJiraHostMenuCommand(AbstractCommand):

    def handler(self, bot, update, *args, **kwargs):
        """Displays supported JIRA hosts for further authorization"""
        button_list = list()
        telegram_id = update.message.chat_id
        user = self._bot_instance.db.get_user_data(telegram_id)
        message = 'On which host do you want to log in?'

        if user:
            authorized_host_url = user.get('host_url')
            allowed_hosts = self._bot_instance.db.get_hosts(user.get('allowed_hosts'))

            for host in allowed_hosts:
                name = host['readable_name']

                # visually highlight if the user is already authorized on the host
                if authorized_host_url == host['url']:
                    name = '· {} ·'.format(name)

                button_list.append(
                    InlineKeyboardButton(
                        name, callback_data='oauth:{}'.format(host['url']))
                )

        if not button_list:
            message = "You haven't specified any hosts. Use /host command for this"

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text=message,
            reply_markup=reply_markup
        )


class LogoutMenuCommand(AbstractCommand):
    positive_answer = 'Yes'
    negative_answer = 'No'

    def handler(self, bot, update, *args, **kwargs):
        """
        Call order: /logout
        """
        button_list = [
            InlineKeyboardButton(
                'Yes', callback_data='logout:{}'.format(self.positive_answer)
            ),
            InlineKeyboardButton(
                'No', callback_data='logout:{}'.format(self.negative_answer)
            ),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text='Are you sure you want to logout? If approved, all credentials '
                 'associated with this user will be deleted.',
            reply_markup=reply_markup
        )
