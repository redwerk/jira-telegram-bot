import logging
from abc import abstractmethod

import requests
from decouple import config

from common.utils import calculate_tracking_time

logger = logging.getLogger()


class BaseNotify:
    api_bot_url = (
        'https://api.telegram.org/bot{}'.format(config('BOT_TOKEN')) +
        '/sendMessage?chat_id={}&text={}&parse_mode=HTML'
    )

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

    @abstractmethod
    def notify(self):
        pass

    def send_to_chat(self, message):
        for chat_id in self.chat_ids:
            url = self.api_bot_url.format(chat_id, message)
            requests.get(url)


class WorklogNotify(BaseNotify):
    """
    Processing updates for Jira worklogs
    Actions: a worklog may be created, updated and deleted
    """
    message_template = 'User {username} {action} spent time {time}h in <a href="{link}">{link_name}</a>'

    def notify(self):
        data = {
            'username': self.update['user']['displayName'],
            'link': '{}/browse/'.format(self.host) + self.issue.upper(),
            'link_name': self.issue.upper(),
        }

        if self.update['issue_event_type_name'] == 'issue_work_logged':
            start_time = int(self.update['changelog']['items'][-1]['from'])
            end_time = int(self.update['changelog']['items'][-1]['to'])
            additional_data = {
                'action': 'logged',
                'time': round(calculate_tracking_time(abs(end_time - start_time)), 2),
            }
            data.update(additional_data)

        elif self.update['issue_event_type_name'] == 'issue_worklog_updated':
            start_time = int(self.update['changelog']['items'][-2]['from'])
            end_time = int(self.update['changelog']['items'][-2]['to'])
            additional_data = {
                'action': 'updated',
                'time': round(calculate_tracking_time(end_time - start_time), 2),
            }
            data.update(additional_data)

        elif self.update['issue_event_type_name'] == 'issue_worklog_deleted':
            start_time = int(self.update['changelog']['items'][-1]['from'])
            end_time = int(self.update['changelog']['items'][-1]['to'])
            additional_data = {
                'action': 'deleted',
                'time': round(calculate_tracking_time(end_time - start_time), 2),
            }
            data.update(additional_data)

        try:
            msg = self.message_template.format(**data)
        except KeyError as e:
            logger.error("Worklog parser can't send a message: {}".format(e))
        else:
            self.send_to_chat(msg)


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
            'link': '{}/browse/'.format(self.host) + self.issue.upper(),
            'link_name': self.issue.upper(),
        }
        msg = self.message_template.format(**data)
        self.send_to_chat(msg)


class IssueNotify(BaseNotify):
    """
    Processing updates for Jira issues
    Actions:
        changing assigne and status
        attaching or deleting files
    """
    message_template = {
        'assignee': 'Issue <a href="{link}">{link_name}</a> was assigned to <b>{user}</b>',
        'status': (
            'User {username} updated status from <b>{old_status}</b> to <b>{new_status}</b> '
            'at <a href="{link}">{link_name}</a>'
        ),
        'Attachment': 'A file <b>{filename}</b> was {action} by {username} in <a href="{link}">{link_name}</a>'
    }

    def notify(self):
        action = self.update['changelog']['items'][0]['field']
        additional_data = dict()
        data = {
            'username': self.update['user']['displayName'],
            'link': '{}/browse/'.format(self.host) + self.issue.upper(),
            'link_name': self.issue.upper(),
        }

        if self.update['issue_event_type_name'] == 'issue_assigned':
            additional_data = {
                'user': self.update['changelog']['items'][0]['toString'],
            }

        elif self.update['issue_event_type_name'] == 'issue_generic':
            additional_data = {
                'old_status': self.update['changelog']['items'][0]['fromString'],
                'new_status': self.update['changelog']['items'][0]['toString'],
            }

        elif self.update['issue_event_type_name'] == 'issue_updated' and action == 'Attachment':
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

        elif self.update['issue_event_type_name'] == 'issue_updated' and action == 'assignee':
            username = self.update['changelog']['items'][0]['toString']
            additional_data = {
                'user': username if username else 'Unassigned',
            }

        data.update(additional_data)
        try:
            msg = self.message_template[action].format(**data)
        except KeyError as e:
            logger.error("Issue parser can't send a message: {}".format(e))
        else:
            self.send_to_chat(msg)


class ProjectNotify(BaseNotify):
    """
    Processing updates for Jira projects
    Actions: a project may be created, updated and deleted
    """
    message_template = 'Project <a href="{link}">{link_name}</a> was {action}'

    def notify(self):
        data = {
            'action': self.update.get('webhookEvent').replace('project_', ''),
            'link': '{}/browse/{}'.format(self.host, self.update['project']['key']),
            'link_name': self.update['project']['key'].upper(),
        }
        msg = self.message_template.format(**data)
        self.send_to_chat(msg)


class WebhookUpdateFactory:
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
