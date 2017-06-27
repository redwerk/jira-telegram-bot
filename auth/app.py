import logging
import os
from logging.config import fileConfig

import jira
import requests
from decouple import config
from flask import Flask, redirect, request, session, url_for
from flask.views import View
from flask_oauthlib.client import OAuth, OAuthException
from oauthlib.oauth1 import SIGNATURE_RSA

from bot.db import MongoBackend
from bot.utils import read_private_key

# commong settings
fileConfig('../logging_config.ini')
bot_url = config('BOT_URL')
db = MongoBackend()
jira_settings = db.get_host_data(config('JIRA_HOST'))

if not jira_settings:
    logging.warning('No setting for {}'.format(config('JIRA_HOST')))
    raise SystemExit

# Flask settings
oauth = OAuth()
app = Flask(__name__)
app.secret_key = config('SECRET_KEY')

# Flask-OAuthlib settings
consumer_key = jira_settings['settings']['consumer_key']
rsa_key_path = os.path.join(config('PRIVATE_KEYS_PATH'), jira_settings['settings']['key_sert'])
base_server_url = config('JIRA_HOST')
request_token_url = '/plugins/servlet/oauth/request-token'
access_token_url = '/plugins/servlet/oauth/access-token'
authorize_url = '/plugins/servlet/oauth/authorize'


jira_app = oauth.remote_app(
    'JT_OAuth',
    base_url=base_server_url,
    request_token_url=base_server_url + request_token_url,
    access_token_url=base_server_url + access_token_url,
    authorize_url=base_server_url + authorize_url,
    consumer_key=consumer_key,
    request_token_method='POST',
    signature_method=SIGNATURE_RSA,
    rsa_key=read_private_key(rsa_key_path),
    access_token_method='POST',
)


class AuthorizeView(View):
    methods = ['GET']
    api_bot_url = 'https://api.telegram.org/bot{}'.format(config('BOT_TOKEN'))

    def dispatch_request(self, telegram_id):
        """Endpoint which saves telegram_id into session and generates an authorization request"""
        session['telegram_id'] = telegram_id
        session['host'] = request.args.get('host')
        callback = url_for('oauth_authorized', next=request.args.get('next') or request.referrer or None)

        try:
            return jira_app.authorize(callback=callback)
        except OAuthException as e:
            logging.warning(e.message)
            self.send_to_chat(session['telegram_id'], e.message)
            return redirect(bot_url)

    @classmethod
    def send_to_chat(cls, chat_id, message):
        """Sends message to user into chat"""
        url = cls.api_bot_url + '/sendMessage?chat_id={}&text={}'.format(chat_id, message)
        requests.get(url)


class OAuthAuthorizedView(View):
    methods = ['GET']

    def dispatch_request(self):
        """Endpoint which gets response after approved or declined an authorization request"""
        transaction_status = None

        try:
            resp = jira_app.authorized_response()
        except OAuthException as e:
            # if the user declined an authorization request
            message = 'Access denied: {}'.format(e.message)
            AuthorizeView.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        oauth_dict = {
            'access_token': resp.get('oauth_token'),
            'access_token_secret': resp.get('oauth_token_secret'),
            'consumer_key': consumer_key,
            'key_cert': read_private_key(rsa_key_path)
        }

        jira_host = db.get_host_data(session['host'])
        user_exists = db.is_user_exists(session['telegram_id'])

        if not jira_host:
            message = 'Settings for the {} are not found in the database'.format(session['host'])
            logging.warning(message)
            AuthorizeView.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        try:
            authed_jira = jira.JIRA(base_server_url, oauth=oauth_dict)
        except jira.JIRAError as e:
            logging.warning('Status: {}, message: {}'.format(e.status_code, e.text))
        else:
            username = authed_jira.myself().get('key')
            if user_exists:
                data = self.update_token_data(username, jira_host['id'],
                                              oauth_dict['access_token'], oauth_dict['access_token_secret'])
                transaction_status = db.update_user(session['telegram_id'], data)
            else:
                data = self.create_user_data(
                    session['telegram_id'], username, jira_host['id'],
                    oauth_dict['access_token'], oauth_dict['access_token_secret']
                )
                transaction_status = db.create_user(data)

        if not transaction_status:
            message = 'Data cannot save into DB. Please try again later.'
            logging.warning("Data didn't save into DB. "
                            "telegram_id: {}, jira_host: {}".format(session['telegram_id'], jira_host['url']))
            AuthorizeView.send_to_chat(session['telegram_id'], message)
            return redirect(bot_url)

        AuthorizeView.send_to_chat(session['telegram_id'], 'You were successfully authorized.')
        return redirect(bot_url)

    @staticmethod
    def update_token_data(username, host_id, access_token, access_token_secret) -> dict:
        """Generates dict of data for updating access tokens"""
        return {
            '{}.username'.format(host_id): username,
            '{}.access_token'.format(host_id): access_token,
            '{}.access_token_secret'.format(host_id): access_token_secret,
        }

    @staticmethod
    def create_user_data(telegram_id, username, host_id, access_token, access_token_secret) -> dict:
        """Generates dict of data for creating a new user"""
        return {
            'telegram_id': telegram_id,
            host_id: {
                'username': username,
                'access_token': access_token,
                'access_token_secret': access_token_secret
            }
        }

    @jira_app.tokengetter
    def get_jira_token(self, token=None):
        return session.get('jira_token')


app.add_url_rule('/authorize/<string:telegram_id>/', view_func=AuthorizeView.as_view('authorize'))
app.add_url_rule('/oauth_authorized', view_func=OAuthAuthorizedView.as_view('oauth_authorized'))

if __name__ == '__main__':
    app.run()
