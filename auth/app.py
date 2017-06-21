from logging.config import fileConfig

import jira
from decouple import config
from flask import Flask, redirect, request, session, url_for
from oauthlib.oauth1 import SIGNATURE_RSA
from flask_oauthlib.client import OAuthException

from auth.modification import ModifiedOAuth
from bot.utils import read_private_key

fileConfig('../logging_config.ini')
oauth = ModifiedOAuth()
app = Flask(__name__)
app.secret_key = config('SECRET_KEY')

bot_url = config('BOT_URL')
consumer_key = config('CONSUMER_KEY')
rsa_key_path = '../private_keys/{}'.format(config('RSA_KEY'))

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
    request_token_params={'signature_method': SIGNATURE_RSA, 'rsa_key': read_private_key(rsa_key_path)},
    access_token_method='POST',
)


@app.route('/authorize/<string:telegram_id>/')
def authorize(telegram_id):
    """Endpoint which saves telegram_id into session and generates an authorization request"""
    session['telegram_id'] = telegram_id
    callback = url_for('oauth_authorized', next=request.args.get('next') or request.referrer or None)

    return jira_app.authorize(callback=callback)


@app.route('/oauth_authorized')
def oauth_authorized():
    """Endpoint which gets response after approved or declined an authorization request"""
    try:
        resp = jira_app.authorized_response()
    except OAuthException as e:
        # if the user declined an authorization request
        return 'Access denied: {}<br><a href={}>Return to Telegram Bot</a>'.format(e.message, bot_url)

    oauth_dict = {
        'access_token': resp.get('oauth_token'),
        'access_token_secret': resp.get('oauth_token_secret'),
        'consumer_key': consumer_key,
        'key_cert': read_private_key(rsa_key_path)
    }

    try:
        authed_jira = jira.JIRA(base_server_url, oauth=oauth_dict)
    except jira.JIRAError as e:
        print(e.status_code)
    else:
        print(authed_jira.myself().get('key'))

    return redirect(bot_url)


@jira_app.tokengetter
def get_jira_token(token=None):
    return session.get('jira_token')


if __name__ == '__main__':
    app.run()
