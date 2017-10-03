from telegram.error import TelegramError


class JiraLoginError(TelegramError):
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
        super(TelegramError, self).__init__()
        self.message = self.login_error.get(status_code, 'Some problems with login')

    def __str__(self):
        return self.message


class JiraConnectionError(TelegramError):
    """Error if jira host does not exist or temporal unavailable"""
    def __init__(self, host):
        super(TelegramError, self).__init__()
        self.jira_host = host

    def __str__(self):
        return "Can't connect to Jira host, please check the host status:\n{}".format(self.jira_host)


class BaseMessageError(TelegramError):
    def __init__(self, message):
        super(TelegramError, self).__init__()
        self.message = message

    def __str__(self):
        return self.message


class JiraReceivingDataError(BaseMessageError):
    """Any errors during receiving data from Jira API"""
    pass


class JiraEmptyData(BaseMessageError):
    """Signal that the response did not return any data to display to the user"""
    pass


class BotAuthError(BaseMessageError):
    """Errors in validating user credentials"""
    pass
