import logging

import jira
from decouple import config

from bot.utils import read_private_key

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
        oauth_dict = JiraBackend.getting_credentials(kwargs)

        try:
            jira_conn = jira.JIRA(
                server=config('JIRA_HOST'),
                oauth=oauth_dict,
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
    def getting_credentials(kwargs: dict) -> (str, str):
        """Forms a dictionary for OAuth authorization"""
        rsa_key = config('PRIVATE_KEYS_PATH') + kwargs.get('key_sert')
        oauth_dict = {
            'access_token': kwargs.get('access_token'),
            'access_token_secret': kwargs.get('access_token_secret'),
            'consumer_key': kwargs.get('consumer_key'),
            'key_cert': read_private_key(rsa_key)
        }

        return oauth_dict

    def check_credentials(self, credentials: dict) -> (bool, int):
        """
        Attempt to authorize the user in the JIRA service.
        :return: Status and code
        """
        oauth_dict = self.getting_credentials(credentials)
        try:
            jira_conn = jira.JIRA(
                server=config('JIRA_HOST'),
                oauth=oauth_dict,
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
            issues_str = '{} {}\n{}'.format(
                issue.key, issue.fields.summary, issue.permalink()
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
    def get_user_issues_by_worklog(self, start_date: str, end_date: str, *args, **kwargs) -> dict:
        """
        Gets issues in which user logged time in selected time interval
        :return: {'issues_id': 'issue_key'}
        """
        jira_conn, username = self._getting_data(kwargs)

        try:
            issues = jira_conn.search_issues(
                'worklogAuthor = "{username}" and worklogDate >= {start_date} '
                'and worklogDate <= {end_date}'.format(
                    username=username, start_date=start_date, end_date=end_date
                ),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error(
                'Failed to get assigned or '
                'watched {} questions:\n{}'.format(username, e)
            )
        else:
            return self.get_issues_id(issues)

        return dict()

    @staticmethod
    def get_issues_id(issues: list) -> dict:
        return {i.id: i.key for i in issues}

    @jira_connect
    def get_worklogs_by_id(self, issues_ids: dict, *args, **kwargs) -> list:
        """
        Gets worklogs by issue dict ids
        :param issues_ids: {'30407': 'PLS-62', '30356': 'PLS-61'}
        :return: list with projects worklogs
        """
        jira_conn = kwargs.get('jira_conn')
        _worklogs = list()

        for _id, key in issues_ids.items():
            try:
                log = jira_conn.worklogs(issue=_id)
            except jira.JIRAError as e:
                logging.error(
                    'Failed to get {} worklog:\n{}'.format(key, e)
                )
            else:
                if log:
                    _worklogs.append(log)
        else:
            return _worklogs

    @staticmethod
    def get_user_worklogs(_worklogs: list, username: str, display_name=False) -> list:
        """
        Gets the only selected user worklogs
        :param _worklogs: list of lists worklogs
        :param username:
        :param display_name: the flag on what attribute to compare
        :return: list of user worklogs
        """
        if display_name:
            return [log for issue in _worklogs for log in issue if log.author.displayName == username]
        else:
            return [log for issue in _worklogs for log in issue if log.author.name == username]

    @jira_connect
    def get_project_issues_by_worklog(self, project: str, start_date: str, end_date: str, *args, **kwargs) -> dict:
        """
        Gets issues by selected project in which someone logged time in selected time interval
        :return: {'issues_id': 'issue_key'}
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            p_issues = jira_conn.search_issues(
                'project = "{project}" and worklogDate >= {start_date} '
                'and worklogDate <= {end_date}'.format(
                    project=project, start_date=start_date, end_date=end_date
                ),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error('Failed to get issues of {}:\n{}'.format(project, e))
        else:
            return self.get_issues_id(p_issues)

        return dict()

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

    @jira_connect
    def get_user_project_issues_by_worklog(self,
                                           user: str,
                                           project: str,
                                           start_date: str,
                                           end_date: str,
                                           *args,
                                           **kwargs) -> dict:
        """
        Gets issues by selected project in which user logged time in selected time interval
        :return: {'issues_id': 'issue_key'}
        """
        jira_conn = kwargs.get('jira_conn')

        try:
            p_issues = jira_conn.search_issues(
                'project = "{project}" and worklogAuthor = "{user}" and worklogDate >= {start_date} '
                'and worklogDate <= {end_date}'.format(
                    project=project, user=user, start_date=start_date, end_date=end_date
                ),
                maxResults=200
            )
        except jira.JIRAError as e:
            logging.error('Failed to get issues of {} in {}:\n{}'.format(user, project, e))
        else:
            return self.get_issues_id(p_issues)

        return dict()
