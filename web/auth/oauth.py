from flask_oauthlib.client import OAuth
from oauthlib.oauth1 import SIGNATURE_RSA
from decouple import config

from lib.utils import read_rsa_key
from ..app import db, logger


class JiraOAuthApp:
    """JiraOAuthApp create jira remote app"""
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
            logger.exception(msg)
            raise AttributeError(msg)

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
