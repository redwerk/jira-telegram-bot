import logging

import jira
from decouple import config

OK_STATUS = 200


def jira_connection(func):
    """
    The decorator creates a connection for each request to Jira, 
    handles the authorization errors and terminates the user session 
    upon completion of the action.
    :param func: function in which interacts with the Jira service
    :return: requested data or an error code
    """
    def wrapper(*args, **kwargs):
        username, password = JiraBackend.getting_credentials(kwargs)

        try:
            jira_conn = jira.JIRA(
                server=config('JIRA_HOST'),
                basic_auth=(username, password),
                max_retries=1
            )
        except jira.JIRAError as e:
            logging.info('{}'.format(e.status_code))
            return False, e.status_code
        else:
            data = func(*args, **kwargs)
            jira_conn.kill_session()
            return data, OK_STATUS

    return wrapper


class JiraBackend(object):
    """
    Interface for working with Jira service
    """

    # description of the error for each action
    login_error = {
        401: 'Invalid credentials',
        403: 'Login is denied due to a CAPTCHA requirement, or any other '
             'reason. Please, login (relogin) into Jira via browser '
             'and try again.',
        409: 'Login is denied due to an unverified email. '
             'The email must be verified by logging in to JIRA through a '
             'browser and verifying the email.'
    }

    @staticmethod
    def getting_credentials(kwargs: dict):
        username = kwargs.get('username', False)
        password = kwargs.get('password', False)

        return username, password

    @staticmethod
    def check_credentials(username: str, password: str):
        try:
            jira_conn = jira.JIRA(
                server=config('JIRA_HOST'),
                basic_auth=(username, password),
                max_retries=1
            )
        except jira.JIRAError as e:
            return False, e.status_code
        else:
            jira_conn.kill_session()
            return True, OK_STATUS

    @jira_connection
    def get_open_tickets(self, *args, **kwargs):
        pass
