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
        self.project = kwargs.get('project_key')
        self.issue = kwargs.get('issue_key')
        self.issue_url = '{}/browse/'.format(host) + self.issue.upper()
        self.project_url = '{}/projects/'.format(host) + '{}/issues'.format(self.project.upper())

    @abstractmethod
    def notify(self):
        pass

    def send_to_chat(self, message):
        for chat_id in self.chat_ids:
            url = self.api_bot_url.format(chat_id, message)
            requests.get(url)


class WorklogNotify(BaseNotify):
    message_template = 'User {username} {action} comment in <a href="{link}">{link_name}</a>'

    def notify(self):
        print(self.update)


class CommentNotify(BaseNotify):
    message_template = 'User {username} {action} comment in <a href="{link}">{link_name}</a>'

    def notify(self):
        username = self.update['comment']['author']['displayName']
        action = self.update.get('webhookEvent').replace('comment_', '')
        msg = self.message_template.format(
            username=username, action=action, link=self.issue_url, link_name=self.issue.upper()
        )
        self.send_to_chat(msg)


class IssueNotify(BaseNotify):
    pass


class ProjectNotify(BaseNotify):
    pass


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
