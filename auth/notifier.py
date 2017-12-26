import logging
import os
import queue
import threading
import time
from abc import abstractmethod

import requests
from decouple import config

from lib.utils import calculate_tracking_time, read_template

logger = logging.getLogger()


class BaseNotify:
    api_bot_url = 'https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}&parse_mode=HTML'

    def __init__(self, update, chat_ids, host, **kwargs):
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
        self.message_queue = queue.Queue()
        self.r_count = 0  # request count

    @abstractmethod
    def notify(self):
        pass

    def prepare_queue(self, message):
        for chat_id in self.chat_ids:
            url = self.api_bot_url.format(config('BOT_TOKEN'), chat_id, message)
            self.message_queue.put(url)

    def send_to_chat(self):
        thread = threading.Thread(target=self._send)
        thread.start()
        thread.join()

    def _send(self):
        while not self.message_queue.empty():
            # https://core.telegram.org/bots/faq#broadcasting-to-users
            # bot will not be able to send more than 20 messages
            # per minute to the same group
            if self.r_count >= 20:
                self.r_count = 0
                time.sleep(60)

            url = self.message_queue.get()
            try:
                status = requests.get(url)
            except requests.RequestException as error:
                logger.error(f'{url}\n{error}')
                self.message_queue.put(url)
            else:
                self.r_count += 1
                if status.status_code != 200:
                    self.message_queue.put(url)
                else:
                    self.message_queue.task_done()


class WorklogNotify(BaseNotify):
    """
    Processing updates for Jira worklogs
    Actions: a worklog may be created, updated and deleted
    """
    work_logged = 'issue_work_logged'
    work_updated = 'issue_worklog_updated'
    work_deleted = 'issue_worklog_deleted'
    message_template = 'User {username} {action} spent time {time}h in <a href="{link}">{link_name}</a>'
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
            self.prepare_queue(msg)
            self.send_to_chat()

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
    message_template = 'User {username} {action} comment in <a href="{link}">{link_name}</a>'

    def notify(self):
        data = {
            'username': self.update['comment']['author']['displayName'],
            'action': self.update.get('webhookEvent').replace('comment_', ''),
            'link': f'{self.host}/browse/{self.issue.upper()}',
            'link_name': self.issue.upper(),
        }
        msg = self.message_template.format(**data)
        self.prepare_queue(msg)
        self.send_to_chat()


class IssueNotify(BaseNotify):
    """
    Processing updates for Jira issues
    Actions:
        changing assigne, status, description and summary
        attaching or deleting files
    """
    data = dict()
    supported_actions = ('issue_assigned', 'issue_generic', 'issue_updated',)
    assigned = 'issue_assigned'
    generic = 'issue_generic'
    updated = 'issue_updated'
    attachment_action = 'Attachment'
    assignee_action = 'assignee'
    message_template = {
        'assignee': read_template(os.path.join('auth', 'templates', 'issue_assignee.txt')),
        'status': read_template(os.path.join('auth', 'templates', 'issue_status.txt')),
        'Attachment': read_template(os.path.join('auth', 'templates', 'issue_attachment.txt')),
        'description': read_template(os.path.join('auth', 'templates', 'issue_desc.txt')),
        'summary': read_template(os.path.join('auth', 'templates', 'issue_summary.txt')),
    }

    def notify(self):
        if self.update['issue_event_type_name'] not in self.supported_actions:
            return

        action = self.update['changelog']['items'][0]['field']
        self.data = {
            'username': self.update['user']['displayName'],
            'link': f'{self.host}/browse/{self.issue.upper()}',
            'link_name': self.issue.upper(),
        }

        if self.update['issue_event_type_name'] == self.assigned:
            self.issue_assigned()
        elif self.update['issue_event_type_name'] == self.generic:
            self.issue_generic()
        elif self.update['issue_event_type_name'] == self.updated and action == self.attachment_action:
            self.file_attachment()
        elif self.update['issue_event_type_name'] == self.updated and action == self.assignee_action:
            self.issue_reasigned()

        try:
            msg = self.message_template[action].substitute(self.data)
        except KeyError as error:
            logger.error(f"Issue parser can't send a message: {error}")
        else:
            self.prepare_queue(msg)
            self.send_to_chat()

    def issue_assigned(self):
        additional_data = {
            'user': self.update['changelog']['items'][0]['toString'],
        }
        self.data.update(additional_data)

    def issue_generic(self):
        additional_data = {
            'old_status': self.update['changelog']['items'][0]['fromString'],
            'new_status': self.update['changelog']['items'][0]['toString'],
        }
        self.data.update(additional_data)

    def file_attachment(self):
        filename = self.update['changelog']['items'][0]['toString']
        if filename:
            additional_data = {
                'filename': filename,
                'action': 'attached',
            }
        else:
            additional_data = {
                'filename': self.update['changelog']['items'][0]['fromString'],
                'action': 'deleted',
            }
        self.data.update(additional_data)

    def issue_reasigned(self):
        username = self.update['changelog']['items'][0]['toString']
        additional_data = {
            'user': username or 'Unassigned',
        }
        self.data.update(additional_data)


class ProjectNotify(BaseNotify):
    """
    Processing updates for Jira projects
    Actions: a project may be created, updated and deleted
    """
    message_template = 'Project <a href="{link}">{link_name}</a> was {action}'

    def notify(self):
        data = {
            'action': self.update.get('webhookEvent').replace('project_', ''),
            'link': f"{self.host}/browse/{self.update['project']['key']}",
            'link_name': self.update['project']['key'].upper(),
        }
        msg = self.message_template.format(**data)
        self.prepare_queue(msg)
        self.send_to_chat()


class UpdateNotifierFactory:
    webhook_event = {
        'jira:worklog_updated': WorklogNotify,
        'jira:issue_updated': IssueNotify,
        'comment_created': CommentNotify,
        'comment_updated': CommentNotify,
        'comment_deleted': CommentNotify,
        'project_created': ProjectNotify,
        'project_updated': ProjectNotify,
        'project_deleted': ProjectNotify,
    }

    @classmethod
    def notify(cls, update, chat_ids, host, **kwargs):
        parser = cls.webhook_event.get(update.get('webhookEvent'))

        if parser:
            parser(update, chat_ids, host, **kwargs).notify()
