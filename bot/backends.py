import logging
from collections import namedtuple
from json.decoder import JSONDecodeError

import jira
import pendulum
import pytz
from jira.resilientsession import ConnectionError

from bot.exceptions import (JiraConnectionError, JiraEmptyData,
                            JiraLoginError, JiraReceivingDataError)

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
        auth_data = kwargs.get('auth_data')
        jira_conn = JiraBackend.check_authorization(
            auth_method=auth_data.auth_method,
            jira_host=auth_data.jira_host,
            credentials=auth_data.credentials,
        )
        kwargs["jira_conn"] = jira_conn
        kwargs["jira_host"] = auth_data.jira_host
        result = func(*args, **kwargs)
        jira_conn.kill_session()
        return result

    return wrapper


class JiraBackend:
    """
    Interface for working with Jira service
    """
    issue_data = namedtuple('IssueData', 'key permalink')

    @staticmethod
    def is_jira_app(host):
        """Determines the ownership on the Jira"""
        try:
            jira_conn = jira.JIRA(
                server=host,
                max_retries=0
            )
        except (jira.JIRAError, ConnectionError, JSONDecodeError):
            # JSONDecodeError - because jira-python does not handle this exception
            return False
        else:
            jira_conn.server_info()
            return True

    @staticmethod
    def check_authorization(auth_method, jira_host, credentials, base_check=None):
        """
        Used to get the connection object.
        If the connection object is not needed - add the base_check flag (the object will be destroyed)
        :param auth_method: basic or oauth
        :param jira_host: https://jira.test.redwerk.com
        :param credentials: different for each methods
        :param base_check: to destroy the object
        :return: Jira connection object
        """
        try:
            if auth_method == 'basic':
                jira_conn = jira.JIRA(
                    server=jira_host,
                    basic_auth=credentials,
                    max_retries=0
                )
            else:
                jira_conn = jira.JIRA(
                    server=jira_host,
                    oauth=credentials,
                    max_retries=0
                )
        except jira.JIRAError as e:
            raise JiraLoginError(e.status_code, jira_host, auth_method, credentials)
        except ConnectionError:
            raise JiraConnectionError(jira_host)
        else:
            if base_check:
                jira_conn.kill_session()
            else:
                return jira_conn

    @jira_connect
    def get_jira_tz(self, *args, **kwargs):
        """Return user timezone or UTC"""
        jira_conn = kwargs.get('jira_conn')
        try:
            tz = jira_conn.myself().get("timeZone")
        except Exception as err:
            logging.exception(str(err))
            tz = pytz.utc.zone

        return tz

    @jira_connect
    def is_user_on_host(self, host, username, *args, **kwargs):
        """Checking the existence of the user on the Jira host"""
        jira_conn = kwargs.get('jira_conn')
        try:
            jira_conn._session.get('{0}/rest/api/2/user?username={1}'.format(host, username))
        except jira.JIRAError as e:
            raise JiraReceivingDataError(e.text)

    @jira_connect
    def is_project_exists(self, host, project, *args, **kwargs):
        """Checking the existence of the project on the Jira host"""
        jira_conn = kwargs.get('jira_conn')

        try:
            jira_conn._session.get('{0}/rest/api/2/project/{1}'.format(host, project.upper()))
        except jira.JIRAError as e:
            raise JiraReceivingDataError(e.text)

    @jira_connect
    def is_issue_exists(self, host, issue, *args, **kwargs):
        """Checking the existence of the issue on the Jira host"""
        jira_conn = kwargs.get('jira_conn')

        try:
            jira_conn._session.get('{0}/rest/api/2/issue/{1}'.format(host, issue))
        except jira.JIRAError as e:
            raise JiraReceivingDataError(e.text)

    @jira_connect
    def get_open_issues(self, username, *args, **kwargs):
        """
        Getting issues assigned to the user
        :return: formatted issues list
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            issues = jira_conn.search_issues(
                'assignee = "{username}" and resolution = Unresolved'.format(
                    username=username
                ),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.exception('Error while getting {} issues:\n{}'.format(username, e))
            raise JiraReceivingDataError(e.text)
        else:
            if not issues:
                raise JiraEmptyData('Woohoo! No unresolved tasks')

            return issues

    @jira_connect
    def get_user_status_issues(self, username, status, *args, **kwargs):
        """
        Getting issues assigned to the user with selected status
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            issues = jira_conn.search_issues(
                'assignee = "{username}" and status = "{status}" and resolution = Unresolved'.format(
                    username=username, status=status
                ),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.exception('Error while getting {} issues:\n{}'.format(username, e))
            raise JiraReceivingDataError(e.text)
        else:
            if not issues:
                raise JiraEmptyData('Woohoo! You do not have any issues')

            return issues

    @jira_connect
    def get_open_project_issues(self, project, *args, **kwargs):
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
            logging.exception('Error while getting unresolved {} issues:\n{}'.format(project, e))
            raise JiraReceivingDataError(e.text)
        else:
            if not issues:
                raise JiraEmptyData("Project <b>{}</b> doesn't have any unresolved tasks".format(project))

            return issues

    @jira_connect
    def get_project_status_issues(self, project, status, *args, **kwargs):
        """
        Gets issues by project with a selected status and status message
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            issues = jira_conn.search_issues(
                'project = "{}" and status = "{}"'.format(project, status),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.exception(
                'Error while getting {} '
                'issues with status = {}:\n{}'.format(project, status, e)
            )
            raise JiraReceivingDataError(e.text)
        else:
            if not issues:
                raise JiraEmptyData("No tasks with <b>«{}»</b> status in <b>{}</b> project ".format(status, project))

            return issues

    @jira_connect
    def get_all_user_worklogs(self, username, start_date, end_date, *args, **kwargs):
        """
        Gets issues in which user logged time in selected time interval
        """
        jira_conn = kwargs.get('jira_conn')
        issues = list()
        jira_start_date = start_date.strftime('%Y-%m-%d')
        jira_end_date = end_date.strftime('%Y-%m-%d')

        try:
            issues = jira_conn.search_issues(
                'worklogAuthor = "{username}" and worklogDate >= {start_date} and worklogDate <= {end_date}'.format(
                    username=username, start_date=jira_start_date, end_date=jira_end_date
                ),
                expand='changelog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            logging.exception(
                'Failed to get assigned or '
                'watched {} questions:\n{}'.format(username, e)
            )
            if not issues:
                raise JiraEmptyData(
                    f'Has no worklogs for <b>{username}</b> from <b>{start_date.to_date_string()}</b> '
                    f'to <b>{end_date.to_date_string()}</b>'
                )

        return self.obtain_worklogs(issues, start_date, end_date, kwargs)

    @jira_connect
    def get_issue_worklogs(self, issue_name, start_date, end_date, *args, **kwargs):
        """
        Gets issue worklogs in selected time interval
        """
        jira_conn = kwargs.get('jira_conn')
        issue = None
        jira_start_date = start_date.strftime('%Y-%m-%d')
        jira_end_date = end_date.strftime('%Y-%m-%d')

        try:
            issue = jira_conn.search_issues(
                'issue = "{}" and worklogDate >= {} and worklogDate <= {}'.format(
                    issue_name, jira_start_date, jira_end_date
                ),
                expand='changelog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            logging.exception('Failed while getting {} issue worklog: {}'.format(issue_name, e))
        else:
            if not issue:
                raise JiraEmptyData(
                    f'Has no worklogs for <b>{issue_name}</b> issue from <b>{start_date.to_date_string()}</b> '
                    f'to <b>{end_date.to_date_string()}</b>'
                )

        return self.obtain_worklogs(issue, start_date, end_date, kwargs)

    @jira_connect
    def get_project_worklogs(self, project, start_date, end_date, *args, **kwargs):
        """
        Gets issues by selected project in which someone logged time in selected time interval
        """
        jira_conn = kwargs.get('jira_conn')
        p_issues = list()
        jira_start_date = start_date.strftime('%Y-%m-%d')
        jira_end_date = end_date.strftime('%Y-%m-%d')

        try:
            p_issues = jira_conn.search_issues(
                'project = "{project}" and worklogDate >= {start_date} and worklogDate <= {end_date}'.format(
                    project=project, start_date=jira_start_date, end_date=jira_end_date
                ),
                expand='changelog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            logging.exception('Failed to get issues of {}:\n{}'.format(project, e))
        if not p_issues:
            raise JiraEmptyData(
                f'Has no worklogs for <b>{project}</b> project from <b>{start_date.to_date_string()}</b> '
                f'to <b>{end_date.to_date_string()}</b>'
            )

        return self.obtain_worklogs(p_issues, start_date, end_date, kwargs)

    def obtain_worklogs(self, issues, start_date, end_date, session_data):
        """
        Returns list of worklogs in dict flat structure

        issue_key: str
        author_name: str
        created: Pendulum datetime object
        time_spent_seconds: int
        """
        all_worklogs = list()
        received_worklogs = list()

        issues_worklog = self.extraction_worklog_ids(issues, start_date, end_date)

        if issues_worklog:
            w_ids = [int(w_id) for issue in issues_worklog.values() for w_id in issue['worklog_ids']]
            received_worklogs = self.request_worklogs_by_id(
                session_data.get('jira_conn'),
                session_data.get('jira_host'),
                w_ids
            )

        for worklog in received_worklogs:
            w_data = {
                'issue_key': issues_worklog.get(worklog['issueId'])['issue_key'],
                'author_name': worklog['author']['name'],
                'created': pendulum.parse(worklog['created']),
                'time_spent_seconds': worklog['timeSpentSeconds'],
            }
            all_worklogs.append(w_data)

        return all_worklogs

    @staticmethod
    def extraction_worklog_ids(issues, start_date, end_date):
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
        worklogs = dict()

        try:
            for issue in issues:
                issue_data = {
                    'issue_key': issue.key,
                    'issue_permalink': issue.permalink(),
                }
                worklog_ids = []

                for history in issue.changelog.histories:
                    creted_date = pendulum.parse(history.created)
                    time_condition = (creted_date >= start_date) and (creted_date <= end_date)

                    for item in history.items:
                        if item.field == 'WorklogId' and time_condition:
                            worklog_ids.append(item.fromString)

                if worklog_ids:
                    issue_data['worklog_ids'] = worklog_ids
                    worklogs[issue.id] = issue_data

        except AttributeError as e:
            logging.exception(e)
        else:
            return worklogs

    @staticmethod
    def request_worklogs_by_id(jira_conn, host, w_ids):
        """
        Gets worklogs by their identifiers making a request for an endpoint that is not supported by the library
        :param jira_conn: auth object for making requests
        :param host: server host
        :param w_ids: list of worklog ids
        :return: dict with data about worklogs
        """
        worklogs = {}
        response = jira_conn._session.post(host + '/rest/api/2/worklog/list', json={'ids': w_ids})

        if response.status_code == OK_STATUS:
            worklogs = response.json()

        return worklogs

    @staticmethod
    def define_user_worklogs(_worklogs, username, name_key):
        """Gets the only selected user worklogs"""
        return [log for log in _worklogs if log.get(name_key) == username]

    @jira_connect
    def get_favourite_filters(self, *args, **kwargs):
        """Return list of favourite filters"""
        jira_conn = kwargs.get('jira_conn')

        try:
            filters = jira_conn.favourite_filters()
        except jira.JIRAError as e:
            logging.exception('Failed to get filters:\n{}'.format(e))
            raise JiraReceivingDataError(e.text)
        else:
            return {f.name: f.id for f in filters}

    @jira_connect
    def get_filter_issues(self, filter_name, filter_id, *args, **kwargs):
        """Returns issues getting by filter id"""
        jira_conn = kwargs.get('jira_conn')

        try:
            issues = jira_conn.search_issues('filter={}'.format(filter_id), maxResults=200)
        except jira.JIRAError as e:
            logging.exception('Failed to get issues by filter:\n{}'.format(e))
            raise JiraReceivingDataError(e.text)
        else:
            if not issues:
                raise JiraEmptyData('No tasks which filtered by <b>«{}»</b>'.format(filter_name))

            return issues
