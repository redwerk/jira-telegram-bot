import json

from flask import request
from flask.views import MethodView

from . import webhooks
from .notifier import notify
from ..app import db


JIRA_AGENT = 'Atlassian HttpClient'


def filters_subscribers(subscribers, project, issue=None):
    """
    Filtering subscribers through its topics: project or issue
    :param subscribers: list of user subscribers info in dictionary type
    :param project: project key e.g. JTB
    :param issue: issue key e.g. JTB-99
    :return: set of chat_ids
    TODO: rewrite this function
    """
    sub_users = list()
    for sub in subscribers:
        sub_topic = sub.get('topic')
        sub_name = sub.get('name')
        sub_chat_id = sub.get('chat_id')
        project_cond = sub_topic == 'project' and project == sub_name

        if project:
            if sub_topic == 'project' and project == sub_name:
                sub_users.append(sub_chat_id)

        if issue:
            if sub_topic == 'issue' and issue == sub_name or project_cond:
                sub_users.append(sub_chat_id)

    return set(sub_users)


class IssueWebhookView(MethodView):
    """Processing updates from Jira issues"""

    def post(self, **kwargs):
        if not request.content_length or JIRA_AGENT not in request.headers['User-Agent']:
            return 'Endpoint is processing only updates from jira webhook', 403

        webhook = db.get_webhook(webhook_id=kwargs.get('webhook_id'))
        if not webhook:
            return 'Unregistered webhook', 403

        subs = db.get_webhook_subscriptions(webhook.get('_id'))
        if not subs.count():
            return 'No subscribers', 200

        jira_update = json.loads(request.data)
        chat_ids = filters_subscribers(subs, kwargs.get('project_key'), kwargs.get('issue_key'))
        notify(jira_update, chat_ids, webhook.get('host_url'), **kwargs)

        return 'OK', 200


class ProjectWebhookView(MethodView):
    """Processing updates from Jira projects"""

    def post(self, **kwargs):
        if not request.content_length or JIRA_AGENT not in request.headers['User-Agent']:
            return 'Endpoint is processing only updates from jira webhook', 403

        webhook = db.get_webhook(webhook_id=kwargs.get('webhook_id'))
        if not webhook:
            return 'Unregistered webhook', 403

        subs = db.get_webhook_subscriptions(webhook.get('_id'))
        if not subs.count():
            return 'No subscribers', 200

        jira_update = json.loads(request.data)
        chat_ids = filters_subscribers(subs, kwargs.get('project_key'))
        notify(jira_update, chat_ids, webhook.get('host_url'), **kwargs)

        return 'OK', 200


webhooks.add_url_rule(
    '/<webhook_id>/<project_key>/',
    view_func=ProjectWebhookView.as_view('project-webhook')
)
webhooks.add_url_rule(
    '/<webhook_id>/<project_key>/<issue_key>/',
    view_func=IssueWebhookView.as_view('issue-webhook')
)
