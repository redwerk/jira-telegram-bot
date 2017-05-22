import logging

import jira
from decouple import config

OK_STATUS = 200


def jira_connect(func):
    """
    The decorator creates a connection for each request to Jira, 
    handles the authorization errors and terminates the user session 
    upon completion of the action.
    :param func: function in which interacts with the Jira service
    :return: requested data and status code
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
            kwargs.update({'jira_conn': jira_conn})
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

    issues_statuses = (
        'Open',
        'In Progress',
        'Reopened',
        'To Do',
        'Testing',
        'Selected for Development',
        'QA',
        'Sales team',
        'Prepare for offer',
    )

    @staticmethod
    def getting_credentials(kwargs: dict):
        username = kwargs.get('username', False)
        password = kwargs.get('password', False)

        return username, password

    @staticmethod
    def check_credentials(username: str, password: str) -> (bool, int):
        """
        Attempt to authorize the user in the JIRA service.
        :param username: username at Jira
        :param password: password at Jira
        :return: Status and code
        """
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

    @staticmethod
    def _getting_data(kwargs: dict) -> (jira.JIRA, str):
        """
        Getting jira_conn and username from kwargs
        :param kwargs: dict
        :return: jira_conn and username
        """
        jira_conn = kwargs.get('jira_conn')
        username = kwargs.get('username')

        return jira_conn, username

    @jira_connect
    def get_open_issues(self, *args, **kwargs) -> list:
        """
        Getting issues assigned to the user
        :return: formatted issues list or empty list
        """
        jira_conn, username = self._getting_data(kwargs)

        issues = jira_conn.search_issues(
            'assignee = {username} and ({statuses})'.format(
                username=username, statuses=self.generate_status_query()
            ),
            maxResults=100
        )

        if issues:
            return self._issues_formatting(issues)

        return list()

    @staticmethod
    def _issues_formatting(issues) -> list:
        """
        Formats tasks by template: issue id, title and permalink
        :param issues: jira issues object
        :return: list of formatted issues
        """
        issues_list = list()

        for issue in issues:
            issues_str = '{} {}\n{}'.format(
                issue.key, issue.fields.summary, issue.permalink()
            )
            issues_list.append(issues_str)

        return issues_list

    def generate_status_query(self) -> str:
        """
        Generating a query string in JQL format from open issues
        :return: 'status = "Open" or status = "To Do"' etc.
        """
        sub_query = ['status = "{}"'.format(s) for s in self.issues_statuses]
        return ' or '.join(sub_query)

