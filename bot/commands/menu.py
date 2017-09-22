from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot import utils

from .base import AbstractCommand


class ChooseDeveloperMenuCommand(AbstractCommand):

    def handler(self, bot, scope, auth_data, *args, **kwargs):
        """Displaying inline keyboard with developers names"""

        buttons = list()
        callback_key = kwargs.get('pattern')
        footer = kwargs.get('footer')

        developers, status = self._bot_instance.jira.get_developers(auth_data=auth_data)

        if not developers:
            bot.edit_message_text(
                text="Sorry, can't get developers list at the moment.",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        for fullname in sorted(developers):
            buttons.append(
                InlineKeyboardButton(text=fullname, callback_data=callback_key.format(fullname))
            )

        footer_button = [
            InlineKeyboardButton('« Back', callback_data=footer)
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

    def handler(self, bot, scope, auth_data, *args, **kwargs):
        """
        Call order: /menu > Issues > Unresolved by project
        Displaying inline keyboard with names of projects
        """
        callback_key = kwargs.get('pattern')
        footer = kwargs.get('footer')

        projects_buttons = list()
        projects, status_code = self._bot_instance.jira.get_projects(auth_data=auth_data)

        if not projects:
            bot.edit_message_text(
                text="Sorry, can't get projects list at the moment.",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        # dynamic keyboard creation
        for project_name in projects:
            projects_buttons.append(
                InlineKeyboardButton(
                    text=project_name,
                    callback_data=callback_key.format(project_name)
                )
            )

        footer_button = [
            InlineKeyboardButton('« Back', callback_data=footer)
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

    def handler(self, bot, scope, auth_data, *args, **kwargs):
        """
        Call order: /menu > Issues > Unresolved by project > Some project
        Displaying inline keyboard with available statuses
        """
        status_buttons = list()
        callback_key = kwargs.get('pattern')
        footer = kwargs.get('footer')
        project = kwargs.get('project')

        statuses, error = self._bot_instance.jira.get_statuses(auth_data=auth_data)

        if not statuses:
            bot.edit_message_text(
                text="Sorry, can't get statuses at the moment",
                chat_id=scope['chat_id'],
                message_id=scope['message_id']
            )
            return

        for status in statuses:
            status_buttons.append(
                InlineKeyboardButton(
                    text=status,
                    callback_data=callback_key.format(status)
                )
            )
        footer_button = [
            InlineKeyboardButton('« Back', callback_data=footer)
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
        message = 'Which host do you want to log in to?'

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
            message = "You haven't specified any hosts. Please, enter Jira host by typing /host jira.yourcompany.com"

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text=message,
            reply_markup=reply_markup
        )


class DisconnectMenuCommand(AbstractCommand):
    positive_answer = 'Yes'
    negative_answer = 'No'

    def handler(self, bot, update, *args, **kwargs):
        """
        /disconnect
        """
        button_list = [
            InlineKeyboardButton(
                'Yes', callback_data='disconnect:{}'.format(self.positive_answer)
            ),
            InlineKeyboardButton(
                'No', callback_data='disconnect:{}'.format(self.negative_answer)
            ),
        ]

        reply_markup = InlineKeyboardMarkup(utils.build_menu(
            button_list, n_cols=2
        ))

        bot.send_message(
            chat_id=update.message.chat_id,
            text='Are you sure you want to log out? All credentials associated with this user will be lost.',
            reply_markup=reply_markup
        )
