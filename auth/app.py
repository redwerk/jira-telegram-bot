import jira
from decouple import config
from flask import Flask, redirect, request, session, url_for
from flask_oauthlib.client import OAuth
from oauthlib.oauth1 import SIGNATURE_RSA

oauth = OAuth()
app = Flask(__name__)
app.secret_key = config('SECRET_KEY')

bot_url = config('BOT_URL')
consumer_key = 'OAuthKey'
rsa_key_path = '../private_keys/jira_test_redwerk_privatekey.pem'

base_server_url = 'https://jira.test.redwerk.com'
request_token_url = '/plugins/servlet/oauth/request-token'
access_token_url = '/plugins/servlet/oauth/access-token'
authorize_url = '/plugins/servlet/oauth/authorize'


def read_privat_key(path):
    key_cert = None

    with open(path, 'r') as f:
        key_cert = f.read()

    return key_cert


jira_app = oauth.remote_app(
    'JT_OAuth',
    base_url=base_server_url,
    request_token_url=base_server_url + request_token_url,
    access_token_url=base_server_url + access_token_url,
    authorize_url=base_server_url + authorize_url,
    consumer_key=consumer_key,
    request_token_method='POST',
    request_token_params={'signature_method': SIGNATURE_RSA, 'rsa_key': read_privat_key(rsa_key_path)},
    access_token_method='POST',
)


@app.route('/authorize/<string:telegram_id>/')
def authorize(telegram_id):
    session['telegram_id'] = telegram_id
    return jira_app.authorize(
        callback=url_for('oauth_authorized', next=request.args.get('next') or request.referrer or None)
    )


@app.route('/oauth_authorized')
@jira_app.authorized_handler
def oauth_authorized(resp):
    oauth_dict = {
        'access_token': resp.get('oauth_token'),
        'access_token_secret': resp.get('oauth_token_secret'),
        'consumer_key': consumer_key,
        'key_cert': read_privat_key(rsa_key_path)
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
