import logging
from collections import namedtuple

import jira
from decouple import config
from jira.resilientsession import ConnectionError, ResilientSession
from oauthlib.oauth1 import SIGNATURE_RSA
from requests_oauthlib import OAuth1

from bot.utils import JIRA_DATE_FORMAT, USER_DATE_FORMAT, add_time, read_rsa_key, to_datetime

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

        oauth = OAuth1(
            auth_data.credentials['consumer_key'],
            rsa_key=auth_data.credentials['key_cert'],
            signature_method=SIGNATURE_RSA,
            resource_owner_key=auth_data.credentials['access_token'],
            resource_owner_secret=auth_data.credentials['access_token_secret']
        )

        # to request a worklogs from an unsupported endpoint
        requests_session = ResilientSession(timeout=20.0)
        requests_session.auth = oauth
        requests_session.verify = True

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
            kwargs.update(
                {
                    'jira_conn': jira_conn,
                    'requests_session': requests_session,
                    'jira_host': auth_data.jira_host
                }
            )
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
                expand='changelog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            logging.error(
                'Failed to get assigned or '
                'watched {} questions:\n{}'.format(username, e)
            )

        return self._obtain_worklogs(issues, start_date, end_date, kwargs)

    def _obtain_worklogs(self, issues, start_date, end_date, session_data):
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
        received_worklogs = list()

        issues_worklog = self._extraction_worklog_ids(issues, start_date, end_date)

        if issues_worklog:
            w_ids = [int(w_id) for issue in issues_worklog.values() for w_id in issue['worklog_ids']]
            received_worklogs = self._request_worklogs_by_id(
                session_data.get('requests_session'),
                session_data.get('jira_host'),
                w_ids
            )

        for worklog in received_worklogs:
            w_data = {
                'issue_key': issues_worklog.get(worklog['issueId'])['issue_key'],
                'issue_permalink': issues_worklog.get(worklog['issueId'])['issue_permalink'],
                'author_displayName': worklog['author']['displayName'],
                'author_name': worklog['author']['name'],
                'created': to_datetime(worklog['created'], JIRA_DATE_FORMAT),
                'time_spent': worklog['timeSpent'],
                'time_spent_seconds': worklog['timeSpentSeconds'],
            }
            all_worklogs.append(w_data)

        return all_worklogs

    @staticmethod
    def _extraction_worklog_ids(issues, start_date, end_date):
        """
        Obtains the identifiers of the vorklogs and combines them in the structure:
        the worklogs relate to the issues in which they are indicated

        {
            '321315': { # issue_id
                'issue_key': 'JTB-19',
                'issue_permalink': 'https://jira.redwerk.com/browse/JTB-19',
                'worklog_ids': ['123', '4235', '213423']
            }
        }

        :param issues: issues with changelog data
        :param start_date: start time interval
        :param end_date: end time interval
        :return: dict of formatted worklog ids
        """
        _worklogs = dict()
        start_datetime = to_datetime(start_date, USER_DATE_FORMAT)
        end_datetime = to_datetime(end_date, USER_DATE_FORMAT)
        end_datetime = add_time(end_datetime, hours=23, minutes=59)

        try:
            for issue in issues:
                issue_data = {
                    'issue_key': issue.key,
                    'issue_permalink': issue.permalink(),
                }
                _worklog_ids = []

                for history in issue.changelog.histories:
                    creted_date = to_datetime(history.created, JIRA_DATE_FORMAT)
                    time_condition = (creted_date >= start_datetime) and (creted_date <= end_datetime)

                    for item in history.items:

                        if item.field == 'WorklogId' and time_condition:
                            _worklog_ids.append(item.fromString)

                if _worklog_ids:
                    issue_data['worklog_ids'] = _worklog_ids
                    _worklogs[issue.id] = issue_data

        except AttributeError as e:
            logging.warning(e)
        else:
            return _worklogs

    @staticmethod
    def _request_worklogs_by_id(session, host, w_ids):
        """
        Gets worklogs by their identifiers making a request for an endpoint that is not supported by the library
        :param session: auth object for making requests
        :param host: server host
        :param w_ids: list of worklog ids
        :return: dict with data about worklogs
        """
        worklogs = {}
        response = session.post(host + '/rest/api/2/worklog/list', json={'ids': w_ids})

        if response.status_code == OK_STATUS:
            worklogs = response.json()

        return worklogs

    @staticmethod
    def define_user_worklogs(_worklogs: list, username: str, name_key: str) -> list:
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
                expand='changelog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            logging.error('Failed to get issues of {}:\n{}'.format(project, e))

        return self._obtain_worklogs(p_issues, start_date, end_date, kwargs)

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
                expand='changelog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            logging.error('Failed to get issues of {} in {}:\n{}'.format(user, project, e))

        return self._obtain_worklogs(p_issues, start_date, end_date, kwargs)

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
