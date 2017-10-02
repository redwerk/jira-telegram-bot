class JiraLoginError(Exception):
    """Login error during login into Jira"""
    login_error = {
        401: 'Invalid credentials',
        403: 'Login is denied due to a CAPTCHA requirement, or any other '
             'reason. Please, login (relogin) into Jira via browser '
             'and try again.',
        409: 'Login is denied due to an unverified email. '
             'The email must be verified by logging in to JIRA through a '
             'browser and verifying the email.'
    }

    def __init__(self, status_code):
        self.message = self.login_error.get(status_code, 'Some problems with login')

    def __str__(self):
        return self.message


class JiraConnectionError(Exception):
    """Error if jira host does not exist or temporal unavailable"""
    def __init__(self, host):
        self.jira_host = host

    def __str__(self):
        return "Can't connect to Jira host, please check the host status:\n{}".format(self.jira_host)


class BaseMessageError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class JiraReceivingDataError(BaseMessageError):
    """Any errors during receiving data from Jira API"""
    pass


class JiraEmptyData(BaseMessageError):
    pass


class BotAuthError(BaseMessageError):
    pass
