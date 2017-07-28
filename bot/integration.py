import logging
from collections import namedtuple

import jira
from decouple import config
from jira.resilientsession import ConnectionError

from bot.utils import JIRA_DATE_FORMAT, read_rsa_key, to_datetime

OK_STATUS = 200


def jira_connect(func):
    """
    The decorator creates a connection for each request to Jira,
    handles the authorization errors and terminates the user session
    upon completion of the action.
    :param func: function in which interacts with the Jira service
    :return: requested data and status code
    """
    def wrapper(*args, **kwargs) -> (list or bool, int):
        auth_data = JiraBackend.getting_credentials(kwargs)

        try:
            jira_conn = jira.JIRA(
                server=auth_data.jira_host,
                oauth=auth_data.credentials,
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


class JiraBackend:
    """
    Interface for working with Jira service
    """
    issue_data = namedtuple('IssueData', 'key permalink')

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
    def getting_credentials(kwargs: dict) -> namedtuple:
        """Forms a namedtuple for OAuth authorization"""
        AuthData = namedtuple('AuthData', 'jira_host credentials')

        oauth_dict = {
            'access_token': kwargs.get('access_token'),
            'access_token_secret': kwargs.get('access_token_secret'),
            'consumer_key': kwargs.get('consumer_key'),
            'key_cert': read_rsa_key(config('PRIVATE_KEY_PATH'))
        }

        return AuthData(jira_host=kwargs.get('url'), credentials=oauth_dict)

    @staticmethod
    def is_jira_app(host: str) -> bool:
        """Determines the ownership on the Jira"""
        try:
            jira_conn = jira.JIRA(
                server=host,
                max_retries=1
            )
        except (jira.JIRAError, ConnectionError) as e:
            return False
        else:
            jira_conn.server_info()
            return True

    def check_credentials(self, credentials: dict) -> (bool, int):
        """
        Attempt to authorize the user in the JIRA service.
        :return: Status and code
        """
        auth_data = self.getting_credentials(credentials)
        try:
            jira_conn = jira.JIRA(
                server=auth_data.jira_host,
                oauth=auth_data.credentials,
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

        try:
            issues = jira_conn.search_issues(
                'assignee = {username} and resolution = Unresolved'.format(
                    username=username
                ),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error(
                'Error while getting {} issues:\n{}'.format(username, e)
            )
        else:
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
            issues_str = '<a href="{permalink}">{key}</a> {summary}'.format(
                key=issue.key, summary=issue.fields.summary, permalink=issue.permalink()
            )
            issues_list.append(issues_str)

        return issues_list

    @jira_connect
    def get_projects(self, *args, **kwargs) -> list:
        """
        Return abbreviation name of the projects
        :return: list of names
        """
        jira_conn = kwargs.get('jira_conn')

        projects = jira_conn.projects()
        return [project.key for project in projects]

    @jira_connect
    def get_open_project_issues(self, project: str, *args, **kwargs) -> list:
        """
        Getting unresolved issues by project
        :param project: abbreviation name of the project
        :return: formatted issues list or empty list
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            issues = jira_conn.search_issues(
                'project = "{}" and resolution = Unresolved'.format(project),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error(
                'Error while getting unresolved '
                '{} issues:\n{}'.format(project, e)
            )
        else:
            return self._issues_formatting(issues)

        return list()

    @jira_connect
    def get_statuses(self, *args, **kwargs) -> list:
        """
        Return names of available statuses
        :return: list of names
        """
        jira_conn = kwargs.get('jira_conn')

        statuses = jira_conn.statuses()
        return [status.name for status in statuses]

    @jira_connect
    def get_project_status_issues(self, project: str, status: str, *args, **kwargs) -> list:
        """
        Gets issues by project with a selected status
        :param project: abbreviation name of the project
        :param status: available status
        :return: formatted issues list or empty list
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            issues = jira_conn.search_issues(
                'project = "{}" and status = "{}"'.format(project, status),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error(
                'Error while getting {} '
                'issues with status = {}:\n{}'.format(project, status, e)
            )
        else:
            return self._issues_formatting(issues)

        return list()

    @jira_connect
    def get_all_user_worklogs(self, start_date: str, end_date: str, *args, **kwargs) -> list:
        """
        Gets issues in which user logged time in selected time interval
        :return: list of worklogs
        """
        jira_conn, username = self._getting_data(kwargs)
        issues = list()

        try:
            issues = jira_conn.search_issues(
                'worklogAuthor = "{username}" and worklogDate >= {start_date} and worklogDate <= {end_date}'.format(
                    username=username, start_date=start_date, end_date=end_date
                ),
                fields='worklog',
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error(
                'Failed to get assigned or '
                'watched {} questions:\n{}'.format(username, e)
            )

        return self._obtain_worklogs(issues)

    @staticmethod
    def _obtain_worklogs(issues: list) -> list:
        """
        Returns list of worklogs in dict flat structure

        issue_key: str
        issue_permalink: str
        author_displayName: str
        author_name: str
        created: datetime
        time_spent: int
        time_spent_seconds: int
        """
        all_worklogs = list()

        for issue in issues:
            try:
                _worklogs = issue.fields.worklog.worklogs
            except AttributeError:
                logging.warning('Worklogs AttributeError in {}'.format(issue.key))
            else:
                for worklog in _worklogs:
                    w_data = {
                        'issue_key': issue.key,
                        'issue_permalink': issue.permalink(),
                        'author_displayName': worklog.author.displayName,
                        'author_name': worklog.author.name,
                        'created': to_datetime(worklog.created, JIRA_DATE_FORMAT),
                        'time_spent': worklog.timeSpent,
                        'time_spent_seconds': worklog.timeSpentSeconds,
                    }
                    all_worklogs.append(w_data)

        return all_worklogs

    @staticmethod
    def get_user_worklogs(_worklogs: list, username: str, name_key: str) -> list:
        """Gets the only selected user worklogs"""
        return [log for log in _worklogs if log.get(name_key) == username]

    @jira_connect
    def get_project_worklogs(self, project: str, start_date: str, end_date: str, *args, **kwargs) -> list:
        """
        Gets issues by selected project in which someone logged time in selected time interval
        :return: list of worklogs
        """
        jira_conn = kwargs.get('jira_conn')
        p_issues = list()

        try:
            p_issues = jira_conn.search_issues(
                'project = "{project}" and worklogDate >= {start_date} and worklogDate <= {end_date}'.format(
                    project=project, start_date=start_date, end_date=end_date
                ),
                fields='worklog',
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error('Failed to get issues of {}:\n{}'.format(project, e))

        return self._obtain_worklogs(p_issues)

    @jira_connect
    def get_user_project_worklogs(self, user, project, start_date, end_date, *args, **kwargs) -> list:
        """
        Gets issues by selected project in which user logged time in selected time interval
        :return: list of worklogs
        """
        jira_conn = kwargs.get('jira_conn')
        p_issues = list()

        try:
            p_issues = jira_conn.search_issues(
                'project = "{project}" and worklogAuthor = "{user}" and worklogDate >= {start_date} '
                'and worklogDate <= {end_date}'.format(
                    project=project, user=user, start_date=start_date, end_date=end_date
                ),
                fields='worklog',
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error('Failed to get issues of {} in {}:\n{}'.format(user, project, e))

        return self._obtain_worklogs(p_issues)

    @jira_connect
    def is_admin_permissions(self, *args, **kwargs) -> bool:
        """Checks if the user has administrator rights (must be added to a specific group)"""
        jira_conn = kwargs.get('jira_conn')

        return jira_conn.my_permissions()['permissions']['ADMINISTER']['havePermission']

    @jira_connect
    def get_developers(self, *args, **kwargs) -> list:
        """Returns a list of developer names"""
        jira_conn = kwargs.get('jira_conn')

        try:
            developers = jira_conn.group_members('jira-developers')
        except jira.JIRAError as e:
            logging.error('Failed to get developers:\n{}'.format(e))
        else:
            return [data['fullname'] for nick, data in developers.items()]

        return list()
