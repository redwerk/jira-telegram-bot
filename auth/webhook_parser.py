from abc import abstractmethod

import requests
from decouple import config


class BaseNotify:
    api_bot_url = (
        'https://api.telegram.org/bot{}'.format(config('BOT_TOKEN')) +
        '/sendMessage?chat_id={}&text={}&parse_mode=HTML'
    )

    def __init__(self, update, chat_ids, host, **kwargs):
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
    message_template = 'User {username} {action} worklog in <a href="{link}">{link_name}</a>'

    def notify(self):
        print(self.update)


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

    def notify(self):
        print(self.update)


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
        'worklog_created': WorklogNotify,
        'worklog_updated': WorklogNotify,
        'worklog_deleted': WorklogNotify,

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
