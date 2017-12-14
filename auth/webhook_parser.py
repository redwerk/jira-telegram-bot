from abc import abstractmethod

import requests
from decouple import config


class BaseNotify:
    api_bot_url = 'https://api.telegram.org/bot{}'.format(config('BOT_TOKEN')) + '/sendMessage?chat_id={}&text={}'

    def __init__(self, update, chat_ids, **kwargs):
        self.update = update
        self.chat_ids = chat_ids

    @abstractmethod
    def notify(self):
        pass

    def send_to_chat(self, chat_ids, message):
        for chat_id in chat_ids:
            url = self.api_bot_url.format(chat_id, message)
            requests.get(url)


class WorklogNotify(BaseNotify):
    message_template = 'User {username} {action} comment in <a href="{link}">{link_name}</a>'

    def notify(self):
        print(self.update)


class CommentNotify(BaseNotify):
    message_template = 'User {username} {action} comment in <a href="{link}">{link_name}</a>'

    def notify(self):
        print(self.update)


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
    def notify(cls, update, chat_ids, **kwargs):
        parser = cls.webhook_event.get(update.get('webhookEvent'))

        if parser:
            parser(update, chat_ids, **kwargs).notify()
