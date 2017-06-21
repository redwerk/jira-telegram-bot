from flask import redirect, session
from flask_oauthlib.client import OAuth, OAuthRemoteApp, _encode
from werkzeug import url_quote


class ModifiedOAuth(OAuth):
    def remote_app(self, name, register=True, **kwargs):
        """Registers a new remote application.

        NOTE: Class OAuthRemoteApp was replaced to create remote applications with a modified method

        :param name: the name of the remote application
        :param register: whether the remote app will be registered

        Find more parameters from :class:`OAuthRemoteApp`.
        """
        remote = ModifiedOAuthRemoteApp(self, name, **kwargs)
        if register:
            assert name not in self.remote_apps
            self.remote_apps[name] = remote
        return remote


class ModifiedOAuthRemoteApp(OAuthRemoteApp):

    def authorize(self, callback=None, state=None, **kwargs):
        """
        Returns a redirect response to the remote authorization URL with
        the signed callback given.

        NOTE: Method changed, that would not add extra parameters to the URL address (private RSA-key etc).

        :param callback: a redirect url for the callback
        :param state: an optional value to embed in the OAuth request.
                      Use this if you want to pass around application
                      state (e.g. CSRF tokens).
        :param kwargs: add optional key/value pairs to the query string
        """
        params = dict(self.request_token_params) or {}
        params.update(**kwargs)

        if self.request_token_url:
            token = self.generate_request_token(callback)[0]
            url = '%s?oauth_token=%s' % (
                self.expand_url(self.authorize_url), url_quote(token)
            )
        else:
            assert callback is not None, 'Callback is required OAuth2'

            client = self.make_client()

            if 'scope' in params:
                scope = params.pop('scope')
            else:
                scope = None

            if isinstance(scope, str):
                # oauthlib need unicode
                scope = _encode(scope, self.encoding)

            if 'state' in params:
                if not state:
                    state = params.pop('state')
                else:
                    # remove state in params
                    params.pop('state')

            if callable(state):
                # state can be function for generate a random string
                state = state()

            session['%s_oauthredir' % self.name] = callback
            url = client.prepare_request_uri(
                self.expand_url(self.authorize_url),
                redirect_uri=callback,
                scope=scope,
                state=state,
                **params
            )
        return redirect(url)
