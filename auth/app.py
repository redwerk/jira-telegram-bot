import logging
from logging.config import fileConfig

from flask import Flask, redirect, request, session, url_for, Response
from flask.views import View
from flask_oauthlib.client import OAuth, OAuthException

import jira
import requests
from decouple import config
from oauthlib.oauth1 import SIGNATURE_RSA

from bot.db import MongoBackend
from common.utils import read_rsa_key
from run import SMTPHandlerNumb

# common settings
fileConfig('./logging_config.ini')
logger = logging.getLogger()
logger.handlers[SMTPHandlerNumb].fromaddr = config('LOGGER_EMAIL')
logger.handlers[SMTPHandlerNumb].toaddrs = [email.strip() for email in config('DEV_EMAILS').split(',')]

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
            logging.exception(msg)
            raise AttributeError

    @property
    def rsa_key_path(self):
        return config('PRIVATE_KEY_PATH')

    @property
    def consumer_key(self):
        return self._jira_settings['consumer_key']

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
            rsa_key=read_rsa_key(self.rsa_key_path),
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
        """
        Endpoint which saves telegram_id into session and
        generates an authorization request
        """

        # TelegramBot, which tries to download a preview of the site to user chat,
        # do not start sending a request for authorization to Jira
        if 'TelegramBot' in request.headers.get('User-Agent'):
            return Response(status=200)

        session['telegram_id'] = telegram_id
        session['host'] = request.args.get('host')
        callback = url_for(
            'oauth_authorized',
            next=request.args.get('next') or request.referrer or None
        )
        try:
            return self.jira_app.authorize(callback=callback)
        except OAuthException as e:
            # unconfirmed host
            jira_host = db.get_host_data(url=request.args.get('host'))
            if jira_host:
                jira_host.update({'is_confirmed': False})
                db.update_host(host_url=jira_host.get('url'), host_data=jira_host)

            logging.exception('{}, Telegram ID: {}, Host: {}'.format(e.message, telegram_id, session['host']))
            message = '{}\nPlease check if you created an Application link in your Jira.\n' \
                      'You can get settings for creating Application link via /oauth command'.format(e.message)
            self.send_to_chat(session['telegram_id'], message)
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
            answer = e.data.get('oauth_problem')

            if answer and answer == 'permission_denied':
                message = 'Authorization request declined by user'

            self.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        oauth_dict = {
            'access_token': resp.get('oauth_token'),
            'access_token_secret': resp.get('oauth_token_secret'),
            'consumer_key': self.jira_app.consumer_key,
            'key_cert': read_rsa_key(self.jira_app.rsa_key_path)
        }

        jira_host = db.get_host_data(session['host'])
        user_exists = db.is_user_exists(session['telegram_id'])

        if not jira_host:
            message = 'No settings found for {} in the database'.format(session['host'])
            logging.exception(message)
            self.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        try:
            authed_jira = jira.JIRA(self.jira_app.base_server_url, oauth=oauth_dict)
        except jira.JIRAError as e:
            logging.exception('Status: {}, message: {}'.format(e.status_code, e.text))
        else:
            username = authed_jira.myself().get('key')
            data = self.get_auth_data(
                session['host'],
                username,
                oauth_dict['access_token'],
                oauth_dict['access_token_secret']
            )
            if not user_exists:
                self.send_to_chat(session['telegram_id'], 'You are not in the database. Just call the /start command')
                return redirect(bot_url)
            else:
                transaction_status = db.update_user(session['telegram_id'], data)

            # host verified
            jira_host.update({'is_confirmed': True})
            db.update_host(host_url=jira_host.get('url'), host_data=jira_host)

        if not transaction_status:
            message = 'Impossible to save data into the database. Please try again later.'
            logging.exception(
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

    def get_auth_data(self, host_url, username, access_token, access_token_secret):
        """Generates dict for creating or updating data about access tokens"""
        return {
            'host_url': host_url,
            'username': username,
            'auth_method': 'oauth',
            'auth.oauth.access_token': access_token,
            'auth.oauth.access_token_secret': access_token_secret
        }


app.add_url_rule('/authorize/<int:telegram_id>/', view_func=AuthorizeView.as_view('authorize'))
app.add_url_rule('/oauth_authorized', view_func=OAuthAuthorizedView.as_view('oauth_authorized'))
