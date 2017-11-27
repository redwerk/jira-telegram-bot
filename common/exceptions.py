from telegram.error import TelegramError


class BaseJTBException(TelegramError):
    def __init__(self, message):
        super(TelegramError, self).__init__()
        self.message = message

    def __str__(self):
        return self.message


class JiraLoginError(BaseJTBException):
    """Login error during login into Jira"""
    login_error = {
        401: 'Invalid credentials or token was rejected.\nPlease try login again',
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


class JiraConnectionError(BaseJTBException):
    """Error if jira host does not exist or temporal unavailable"""
    def __init__(self, host):
        super(TelegramError, self).__init__()
        self.message = "Can't connect to Jira host, please check the host status:\n{}".format(host)


class JiraReceivingDataError(BaseJTBException):
    """Any errors during receiving data from Jira API"""
    pass


class JiraEmptyData(BaseJTBException):
    """Signal that the response did not return any data to display to the user"""
    pass


class BotAuthError(BaseJTBException):
    """Errors in validating user credentials"""
    pass


class SendMessageHandlerError(BaseJTBException):
    """Error in logic according to sending messages"""
    pass
