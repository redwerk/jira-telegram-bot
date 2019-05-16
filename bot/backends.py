import logging
from collections import namedtuple
from json.decoder import JSONDecodeError
from urllib.parse import quote

import jira
import pendulum
import pytz
from jira.resilientsession import ConnectionError
from requests.status_codes import codes as status_codes

from lib import utils
from bot.exceptions import (JiraConnectionError, JiraInfoException, JiraLoginError,
                            JiraReceivingDataException)


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
    def is_user_on_host(self, username, *args, **kwargs):
        """Checking the existence of the user on the Jira host"""
        jira_conn = kwargs.get('jira_conn')
        try:
            jira_conn.user(quote(username))
        except jira.JIRAError as e:
            if e.status_code == status_codes.NOT_FOUND:
                message = f"'{username}' does not exist"
                raise JiraInfoException(message)
            else:
                message = e.text
                raise JiraReceivingDataException(f"getting user {username} on host", message)

    @jira_connect
    def is_project_exists(self, project, *args, **kwargs):
        """Checking the existence of the project on the Jira host"""
        jira_conn = kwargs.get('jira_conn')
        try:
            jira_conn.project(project.upper())
        except jira.JIRAError as e:
            if e.status_code == status_codes.NOT_FOUND:
                message = f"Project key '{project.upper()}' does not exist"
                raise JiraInfoException(message)
            else:
                message = e.text
                raise JiraReceivingDataException(f"checking existence of project {project}", message)

    @jira_connect
    def is_issue_exists(self, issue, *args, **kwargs):
        """Checking the existence of the issue on the Jira host"""
        jira_conn = kwargs.get('jira_conn')
        try:
            jira_conn.issue(issue)
        except jira.JIRAError as e:
            if e.status_code == status_codes.NOT_FOUND:
                message = f"Issue '{issue}' doesn't exist"
                raise JiraInfoException(message)
            else:
                raise JiraReceivingDataException(f"checking existence of issue {issue}", e.text)

    @jira_connect
    def is_status_exists(self, status, *args, **kwargs):
        """Checking the existence of the status on the Jira host"""
        jira_conn = kwargs.get('jira_conn')
        try:
            jira_conn.status(status.capitalize())
        except jira.JIRAError as e:
            if e.status_code == status_codes.NOT_FOUND:
                message = f"Value '{status}' does not exist."
                raise JiraInfoException(message)
            else:
                raise JiraReceivingDataException(f"checking existence of status {status}", e.text)

    @jira_connect
    def get_issues(self, username, resolution=None, *args, **kwargs):
        """
        Getting issues assigned to the user
        :param username: username in JIRA
        :type username: str
        :param resolution: issues resolution status
        :type resolution: str
        :return: formatted issues list
        """
        jira_conn = kwargs.get('jira_conn')
        try:
            jql = f'assignee = "{quote(username)}"'
            if resolution:
                jql += f' and resolution = {resolution}'
            jql += ' ORDER BY updated'
            issues = jira_conn.search_issues(jql, maxResults=1000)
        except jira.JIRAError as e:
            raise JiraReceivingDataException(f"getting issues for {username} with {jql}", e.text)
        else:
            if not issues:
                raise JiraInfoException("'{}' doesn't have any unresolved issues".format(username))
            return issues

    @jira_connect
    def get_user_status_issues(self, username, status, resolution=None, *args, **kwargs):
        """
        Getting issues assigned to the user with selected status
        """
        jira_conn = kwargs.get('jira_conn')
        try:
            jql = f'assignee = "{quote(username)}" and status = "{status}"'
            if resolution:
                jql += f' and resolution = {resolution}'
            jql += ' ORDER BY updated'
            issues = jira_conn.search_issues(jql, maxResults=1000)
        except jira.JIRAError as e:
            message = e.text
            raise JiraReceivingDataException(f"getting issues for user {username} with {jql}", message)
        else:
            if not issues:
                raise JiraInfoException("'{}' doesn't have any unresolved issues".format(username))

            return issues

    @jira_connect
    def get_project_issues(self, project, resolution=None, *args, **kwargs):
        """
        Getting issues by project
        :param project: abbreviation name of the project
        :param resolution: issues resolution status
        :type resolution: str
        :return: formatted issues list or empty list
        """
        jira_conn = kwargs.get('jira_conn')
        try:
            jql = f'project = "{project}"'
            if resolution:
                jql += f' and resolution = {resolution}'
            jql += ' ORDER BY updated'
            issues = jira_conn.search_issues(jql, maxResults=1000)
        except jira.JIRAError as e:
            # Very specific error, status code doesn't differentiate
            if e.status_code == status_codes.BAD_REQUEST:
                message = "There are no tickets in this project"
                raise JiraInfoException(message)
            else:
                raise JiraReceivingDataException(f"getting project issues for {project} with {jql}", e.text)
        else:
            if not issues:
                raise JiraInfoException(f"Project <b>{project}</b> doesn't have any unresolved tasks")

            return issues

    @jira_connect
    def get_project_status_issues(self, project, status, resolution=None, *args, **kwargs):
        """
        Gets issues by project with a selected status and status message
        """
        jira_conn = kwargs.get('jira_conn')
        try:
            jql = f'project = "{project}" and status = "{status}"'
            if resolution:
                jql += f' and resolution = {resolution}'
            jql += ' ORDER BY updated'
            issues = jira_conn.search_issues(jql, maxResults=1000)
        except jira.JIRAError as e:
            raise JiraReceivingDataException(f"getting project status issues for {project} with {jql}", e.text)
        else:
            if not issues:
                raise JiraInfoException(
                    "No tasks with <b>«{}»</b> status in <b>{}</b> project ".format(status, project)
                )

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
            jql = 'worklogAuthor = "{username}" and worklogDate >= {start_date} and worklogDate <= {end_date}'.format(
                username=quote(username), start_date=jira_start_date, end_date=jira_end_date,
            )
            issues = jira_conn.search_issues(
                jql,
                expand='changelog',
                fields='worklog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            raise JiraReceivingDataException(f"getting all user worklogs for {username} with {jql}", e.text)
        else:
            if not issues:
                raise JiraInfoException(
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
            jql = 'issue = "{}" and worklogDate >= {} and worklogDate <= {}'.format(
                issue_name, jira_start_date, jira_end_date,
                )
            issue = jira_conn.search_issues(
                jql,
                expand='changelog',
                fields='worklog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            raise JiraReceivingDataException(f"getting issue worklogs for {issue_name} with {jql}")
        else:
            if not issue:
                raise JiraInfoException(
                    f'Has no worklogs for <b>{issue_name}</b> issue from <b>{start_date.to_date_string()}</b> '
                    f'to <b>{end_date.to_date_string()}</b>'
                )

        return self.calculate_spent_time(issue, start_date, end_date, kwargs)

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
            jql = 'project = "{project}" and worklogDate >= {start_date} and worklogDate <= {end_date}'.format(
                project=project, start_date=jira_start_date, end_date=jira_end_date,
            )
            p_issues = jira_conn.search_issues(
                jql,
                expand='changelog',
                fields='worklog',
                maxResults=1000
            )
        except jira.JIRAError as e:
            raise JiraReceivingDataException(f"getting project worklogs for {project} with {jql}", e.text)
        else:
            if not p_issues:
                raise JiraInfoException(
                    f'Has no worklogs for <b>{project}</b> project from <b>{start_date.to_date_string()}</b> '
                    f'to <b>{end_date.to_date_string()}</b>'
                )

            return self.calculate_spent_time(p_issues, start_date, end_date, kwargs)

    @staticmethod
    def calculate_spent_time(issues, start_date, end_date, session_data):
        jira_conn = session_data['jira_conn']
        spent_time = 0
        for issue in issues:
            if issue.fields is None:
                continue
            if issue.fields.worklog.total > issue.fields.worklog.maxResults:
                received_worklogs = jira_conn.worklogs(issue.id)  # additional request to JIRA API
            else:
                received_worklogs = issue.fields.worklog.worklogs

            for worklog in received_worklogs:
                worklog_date = pendulum.parse(worklog.started)
                if worklog_date < start_date or worklog_date > end_date:
                    continue

                spent_time += utils.calculate_tracking_time(worklog.timeSpentSeconds)

        return spent_time

    @staticmethod
    def obtain_worklogs(issues, start_date, end_date, session_data):
        """
        Returns list of worklogs in dict flat structure

        issue_key: str
        author_name: str
        started: Pendulum datetime object
        created: Pendulum datetime object
        time_spent_seconds: int
        """
        issue_keys = dict()
        all_worklogs = list()
        received_worklogs = list()
        jira_conn = session_data['jira_conn']
        for issue in issues:
            if issue.fields is None:
                continue
            if issue.fields.worklog.total > issue.fields.worklog.maxResults:
                received_worklogs += jira_conn.worklogs(issue.id)  # additional request to JIRA API
            else:
                received_worklogs += issue.fields.worklog.worklogs

            issue_keys[issue.id] = issue.key

        for worklog in received_worklogs:
            worklog_date = pendulum.parse(worklog.started)
            if worklog_date < start_date or worklog_date > end_date:
                continue
            w_data = {
                'issue_key': issue_keys[worklog.issueId],
                'author_name': worklog.author.name,
                'created': pendulum.parse(worklog.created),
                'started': worklog_date,
                'time_spent_seconds': worklog.timeSpentSeconds,
            }
            all_worklogs.append(w_data)

        return all_worklogs

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
            raise JiraReceivingDataException("getting favourite filters", e.text)
        else:
            return {f.name: f.id for f in filters}

    @jira_connect
    def get_filter_issues(self, filter_name, filter_id, *args, **kwargs):
        """Returns issues getting by filter id"""
        jira_conn = kwargs.get('jira_conn')
        try:
            jql = 'filter={}'.format(filter_id)
            issues = jira_conn.search_issues(jql, maxResults=1000)
        except jira.JIRAError as e:
            raise JiraReceivingDataException(f"getting filter issues for {filter_name} with {jql}", e.text)
        else:
            if not issues:
                raise JiraInfoException('No tasks which filtered by <b>«{}»</b>'.format(filter_name))

            return issues

    @jira_connect
    def get_webhooks(self, host, *args, **kwargs):
        """
        Returns issues getting by filter id
        :param host: server host
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            response = jira_conn._session.get(host + '/rest/webhooks/1.0/webhook')
        except jira.JIRAError as e:
            raise JiraReceivingDataException(f"getting webhooks for {host}", e.text)
        else:
            return response.json()
