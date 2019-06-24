import os
from abc import ABCMeta, abstractmethod

from decouple import config

from lib.utils import calculate_tracking_time, read_template
from .tasks import send_message
from ..app import logger


TEMPLATES_DIR = os.path.join('web', 'webhooks', 'templates')
BOT_API = 'https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}&parse_mode=HTML'


def broadcast(urls):
    """Broadcasting messaging.
    :param urls: prepared urls to telegram API
    :type urls: list
    """
    for url in urls:
        send_message.delay(url)


class BaseNotify(metaclass=ABCMeta):

    def __init__(self, update, chat_ids, host, db, **kwargs):
        """
        :param update: full update in dictionary format
        :param chat_ids: set of string chat ids for delivering notifications
        :param host: host from what the update was delivered
        :param kwargs: project_key and issue_key
        """
        self.update = update
        self.chat_ids = chat_ids
        self.host = host
        self.project = kwargs.get('project_key')
        self.issue = kwargs.get('issue_key')
        self.db = db

    @abstractmethod
    def notify(self):
        pass

    def prepare_messages(self, messages):
        """Generates links with messages for sending into chats"""
        urls = list()
        if not isinstance(messages, list):
            messages = [messages]

        for chat_id in self.chat_ids:
            for m in messages:
                urls.append(BOT_API.format(config('BOT_TOKEN'), chat_id, m))
        return urls


class WorklogNotify(BaseNotify):
    """
    Processing updates for Jira worklogs
    Actions: a worklog may be created, updated and deleted
    """
    work_logged = 'issue_work_logged'
    work_updated = 'issue_worklog_updated'
    work_deleted = 'issue_worklog_deleted'
    message_template = 'User <b>{username}</b> {action} spent time {time}h in <a href="{link}">{link_name}</a>'
    data = dict()

    def notify(self):
        self.data = {
            'username': self.update['user']['displayName'],
            'link': f'{self.host}/browse/{self.issue.upper()}',
            'link_name': self.issue.upper(),
        }

        if self.update['issue_event_type_name'] == self.work_logged:
            self.worklog_logged()
        elif self.update['issue_event_type_name'] == self.work_updated:
            self.worklog_updated()
        elif self.update['issue_event_type_name'] == self.work_deleted:
            self.worklog_deleted()

        try:
            msg = self.message_template.format(**self.data)
        except KeyError as error:
            logger.error(f"Worklog parser can't send a message: {error}")
        else:
            urls = self.prepare_messages(msg)
            broadcast(urls)

    def worklog_logged(self):
        start_time = int(self.update['changelog']['items'][-1]['from'])
        end_time = int(self.update['changelog']['items'][-1]['to'])
        additional_data = {
            'action': 'logged',
            'time': round(calculate_tracking_time(abs(end_time - start_time)), 2),
        }
        self.data.update(additional_data)

    def worklog_updated(self):
        start_time = int(self.update['changelog']['items'][-2]['from'])
        end_time = int(self.update['changelog']['items'][-2]['to'])
        additional_data = {
            'action': 'updated',
            'time': round(calculate_tracking_time(end_time - start_time), 2),
        }
        self.data.update(additional_data)

    def worklog_deleted(self):
        start_time = int(self.update['changelog']['items'][-1]['from'])
        end_time = int(self.update['changelog']['items'][-1]['to'])
        additional_data = {
            'action': 'deleted',
            'time': round(calculate_tracking_time(end_time - start_time), 2),
        }
        self.data.update(additional_data)


class CommentNotify(BaseNotify):
    """
    Processing updates for Jira comments
    Actions: a comment may be created, updated and deleted
    """
    message_template = 'User <b>{username}</b> {action} comment in <a href="{link}">{link_name}</a>'

    def notify(self):
        data = {
            'username': self.update['comment']['author']['displayName'],
            'action': self.update.get('webhookEvent').replace('comment_', ''),
            'link': f'{self.host}/browse/{self.issue.upper()}',
            'link_name': self.issue.upper(),
        }
        msg = self.message_template.format(**data)
        urls = self.prepare_messages(msg)
        broadcast(urls)


class IssueNotify(BaseNotify):
    """
    Processing updates for Jira issues
    Actions:
        changing assignee, status, description and summary
        attaching or deleting files
    """
    supported_actions = ('issue_assigned', 'issue_generic', 'issue_updated',)
    assigned = 'issue_assigned'
    generic = 'issue_generic'
    updated = 'issue_updated'

    attachment_action = 'Attachment'
    assignee_action = 'assignee'
    status_action = 'status'
    resolution_action = 'resolution'

    message_template = {
        'assignee': os.path.join(TEMPLATES_DIR, 'issue_assignee.txt'),
        'status': os.path.join(TEMPLATES_DIR, 'issue_status.txt'),
        'Attachment': os.path.join(TEMPLATES_DIR, 'issue_attachment.txt'),
        'description': os.path.join(TEMPLATES_DIR, 'issue_desc.txt'),
        'summary': os.path.join(TEMPLATES_DIR, 'issue_summary.txt'),
        'resolution': os.path.join(TEMPLATES_DIR, 'issue_resolution.txt'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []
        self.generic_data = {}

    def notify(self):
        if self.update['issue_event_type_name'] not in self.supported_actions:
            return

        self.generic_data = {
            'username': self.update['user']['displayName'],
            'link': f'{self.host}/browse/{self.issue.upper()}',
            'link_name': self.issue.upper(),
        }

        # in one issue update may be coming several items
        for item in self.update['changelog']['items']:
            field = item.get('field')
            template = self.message_template.get(field)
            if not template:
                continue

            if self.update['issue_event_type_name'] == self.assigned:
                self.issue_assigned(item, template)
            elif self.update['issue_event_type_name'] == self.generic and field == self.status_action:
                self.issue_status(item, template)
            elif self.update['issue_event_type_name'] == self.generic and field == self.resolution_action:
                self.issue_resolution(item, template)
            elif self.update['issue_event_type_name'] == self.updated and field == self.attachment_action:
                self.file_attachment(item, template)
            elif self.update['issue_event_type_name'] == self.updated and field == self.assignee_action:
                self.issue_reassigned(item, template)
            else:
                text = read_template(template)
                self.messages.append(text.substitute(**self.generic_data))

        urls = self.prepare_messages(self.messages)
        broadcast(urls)

    def issue_assigned(self, item, template):
        data = {
            'user': item.get('toString'),
        }
        data.update(self.generic_data)
        template = read_template(template)
        self.messages.append(template.substitute(**data))

    def issue_status(self, item, template):
        data = {
            'old_status': item.get('fromString'),
            'new_status': item.get('toString'),
        }
        data.update(self.generic_data)
        template = read_template(template)
        self.messages.append(template.substitute(**data))

    def issue_resolution(self, item, template):
        old_resolution = item.get('fromString')
        new_resolution = item.get('toString')
        data = {
            'old_resolution': old_resolution or 'Unresolved',
            'new_resolution': new_resolution or 'Unresolved',
        }
        data.update(self.generic_data)
        template = read_template(template)
        self.messages.append(template.substitute(**data))

    def file_attachment(self, item, template):
        filename = item.get('toString')
        if filename:
            data = {
                'filename': filename,
                'action': 'attached',
            }
        else:
            data = {
                'filename': item.get('fromString'),
                'action': 'deleted',
            }
        data.update(self.generic_data)
        template = read_template(template)
        self.messages.append(template.substitute(**data))

    def issue_reassigned(self, item, template):
        username = item.get('toString')
        data = {
            'user': username or 'Unassigned',
        }
        data.update(self.generic_data)
        template = read_template(template)
        self.messages.append(template.substitute(**data))


class ProjectNotify(BaseNotify):
    """
    Processing updates for Jira projects
    Actions: a project may be created, updated and deleted
    """
    message_template = os.path.join(TEMPLATES_DIR, 'issue_created.txt')

    def notify(self):
        data = {
            'action': self.update.get('webhookEvent').replace('project_', ''),
            'link': f"{self.host}/browse/{self.update['project']['key']}",
            'link_name': self.update['project']['key'].upper(),
        }
        text = read_template(self.message_template)
        message = text.substitute(**data)
        urls = self.prepare_messages(message)
        broadcast(urls)


class ProjectIssueNotify(BaseNotify):
    message_template = {
        'issue_created': os.path.join(TEMPLATES_DIR, 'issue_created.txt'),
        'issue_deleted': os.path.join(TEMPLATES_DIR, 'issue_deleted.txt'),
        'issue_deleted_unsubscribed': os.path.join(TEMPLATES_DIR, 'issue_deleted_unsubscribed.txt')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def notify(self):
        issue = self.update['issue']['key']
        _, action = self.update['webhookEvent'].split(":")
        for chat_id in self.chat_ids:
            if action == 'issue_deleted':
                issue_subscribed = self.db.get_subscription(chat_id, issue)
                if issue_subscribed:
                    action = 'issue_deleted_unsubscribed'
                    self.db.delete_subscription(chat_id, issue)
            template = self.message_template[action]
            text = read_template(template)
            data = {
                "issue_link": f"{self.host}/browse/{issue}",
                "issue_name": issue
            }
            message = text.substitute(**data)
            self.messages.append(message)
        urls = self.prepare_messages(self.messages)
        broadcast(urls)


class NotifierFactory:
    events = {
        'jira:worklog_updated': WorklogNotify,
        'jira:issue_updated': IssueNotify,
        'comment_created': CommentNotify,
        'comment_updated': CommentNotify,
        'comment_deleted': CommentNotify,
        'project_created': ProjectNotify,
        'project_updated': ProjectNotify,
        'project_deleted': ProjectNotify,
        'jira:issue_created': ProjectIssueNotify,
        'jira:issue_deleted': ProjectIssueNotify,
    }

    @classmethod
    def get_notifier(cls, event):
        return cls.events.get(event)


def notify(update, chat_ids, host, db, **kwargs):
    """Send broadcast notification"""
    event = update.get('webhookEvent')
    notifier = NotifierFactory.get_notifier(event)
    if notifier:
        notifier(update, chat_ids, host, db, **kwargs).notify()
