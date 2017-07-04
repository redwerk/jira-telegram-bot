import logging
import os
from logging.config import fileConfig

from flask import Flask, redirect, request, session
from flask.views import View
from flask_oauthlib.client import OAuth, OAuthException

import jira
import requests
from decouple import config
from oauthlib.oauth1 import SIGNATURE_RSA

from bot.db import MongoBackend
from bot.utils import read_private_key

# commong settings
fileConfig('./logging_config.ini')
bot_url = config('BOT_URL')
db = MongoBackend()


# Flask settings
app = Flask(__name__)
app.secret_key = config('SECRET_KEY')


class JiraOAuthApp:
    """
    JiraOAuthApp create jira remote app.
    """
    request_token_url = '/plugins/servlet/oauth/request-token'
    access_token_url = '/plugins/servlet/oauth/access-token'
    authorize_url = '/plugins/servlet/oauth/authorize'

    def __init__(self, host, *args, **kwargs):
        self._oauth = OAuth()
        self._base_server_url = host
        self._jira_settings = db.get_host_data(host)
        # host validation
        if not self._jira_settings:
            msg = 'No setting for {}'.format(host)
            logging.warning(msg)
            raise AttributeError

    @property
    def rsa_key_path(self):
        rsa_key = os.path.join(
            config('PRIVATE_KEYS_PATH'),
            self._jira_settings['settings']['key_sert']
        )
        return rsa_key

    @property
    def consumer_key(self):
        return self._jira_settings['settings']['consumer_key']

    def create_remote_app(self):
        # create app
        app = self._oauth.remote_app(
            'JT_OAuth',
            base_url=self._base_server_url,
            request_token_url=self._base_server_url + self.request_token_url,
            access_token_url=self._base_server_url + self.access_token_url,
            authorize_url=self._base_server_url + self.authorize_url,
            consumer_key=self.consumer_key,
            request_token_method='POST',
            signature_method=SIGNATURE_RSA,
            rsa_key=read_private_key(self.rsa_key_path),
            access_token_method='POST',
        )
        # set attributes
        app.base_server_url = self._base_server_url
        app.rsa_key_path = self.rsa_key_path
        app.consumer_key = self.consumer_key

        return app


class OAuthJiraBaseView(View):

    def get_jira_app(self):
        # create new remote jira app
        host = session.get('host')
        jira_app = JiraOAuthApp(host).create_remote_app()
        jira_app.tokengetter(self.get_jira_token)
        return jira_app

    def get_jira_token(self, token=None):
        return session.get('jira_token')

    def __getattr__(self, name):
        # Create jira_app attribute
        if name == "jira_app":
            self.jira_app = self.get_jira_app()
            return self.jira_app

        return super(OAuthJiraBaseView, self).__getattr__(name)


class SendToChatMixin:
    """
    Send message to user into chat.
    """
    querystring = '/sendMessage?chat_id={}&text={}'
    api_bot_url = 'https://api.telegram.org/bot{}'.format(config('BOT_TOKEN'))

    def send_to_chat(self, chat_id, message):
        url = self.api_bot_url + self.querystring.format(chat_id, message)
        requests.get(url)


class AuthorizeView(SendToChatMixin, OAuthJiraBaseView):
    methods = ['GET']

    def dispatch_request(self, telegram_id):
        # Endpoint which saves telegram_id into session and
        # generates an authorization request
        session['telegram_id'] = telegram_id
        session['host'] = request.args.get('host')
        callback = '{}/oauth_authorized'.format(config('OAUTH_SERVICE_URL'))
        try:
            return self.jira_app.authorize(callback=callback)
        except OAuthException as e:
            logging.warning(e.message)
            self.send_to_chat(session['telegram_id'], e.message)
            return redirect(bot_url)


class OAuthAuthorizedView(SendToChatMixin, OAuthJiraBaseView):
    """
    Endpoint which gets response after approved or declined an authorization request.
    """
    methods = ['GET']

    def dispatch_request(self):
        transaction_status = None

        try:
            resp = self.jira_app.authorized_response()
        except OAuthException as e:
            # if the user declined an authorization request
            message = 'Access denied: {}'.format(e.message)
            self.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        oauth_dict = {
            'access_token': resp.get('oauth_token'),
            'access_token_secret': resp.get('oauth_token_secret'),
            'consumer_key': self.jira_app.consumer_key,
            'key_cert': read_private_key(self.jira_app.rsa_key_path)
        }

        jira_host = db.get_host_data(session['host'])
        user_exists = db.is_user_exists(session['telegram_id'])

        if not jira_host:
            message = 'Settings for the {} are not found in the database'.format(session['host'])
            logging.warning(message)
            self.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        try:
            authed_jira = jira.JIRA(self.jira_app.base_server_url, oauth=oauth_dict)
        except jira.JIRAError as e:
            logging.warning('Status: {}, message: {}'.format(e.status_code, e.text))
        else:
            username = authed_jira.myself().get('key')
            data = self.save_token_data(
                session['telegram_id'],
                username,
                jira_host['url'],
                oauth_dict['access_token'],
                oauth_dict['access_token_secret']
            )
            if user_exists:
                transaction_status = db.update_user(session['telegram_id'], data)
            else:
                transaction_status = db.create_user(data)

        if not transaction_status:
            message = 'Data cannot save into DB. Please try again later.'
            logging.warning(
                "Data didn't save into DB. "
                "telegram_id: {}, jira_host: {}".format(session['telegram_id'], jira_host['url'])
            )
            self.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        self.send_to_chat(
            session['telegram_id'],
            'You were successfully authorized in {}'.format(session.get('host', 'Jira'))
        )
        return redirect(bot_url)

    def save_token_data(self, telegram_id, username, host_url, access_token, access_token_secret):
        """Generates dict for creating or updating data about access tokens"""
        return {
            'telegram_id': telegram_id,
            'host_url': host_url,
            'username': username,
            'access_token': access_token,
            'access_token_secret': access_token_secret
        }


app.add_url_rule('/authorize/<string:telegram_id>/', view_func=AuthorizeView.as_view('authorize'))
app.add_url_rule('/oauth_authorized', view_func=OAuthAuthorizedView.as_view('oauth_authorized'))
