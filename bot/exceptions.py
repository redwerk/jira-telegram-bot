from telegram.error import TelegramError

from lib.db import MongoBackend


class BaseJTBException(TelegramError):
    def __init__(self, message):
        super(TelegramError, self).__init__()
        self.message = message

    def __str__(self):
        return self.message


class JiraLoginError(BaseJTBException):
    """Login error during login into Jira"""
    login_error = {
        401: 'Invalid credentials or token was rejected.\nYou can try the following actions:\n'
             '1. If you logged in already, please try to use /disconnect command and log in again.\n'
             '2. Update a previously created Application link (/disconnect, /oauth).\n'
             '3. If you are connecting with email as a login, please try to use username instead.\n'
             '4. Try to connect using /oauth',
        403: 'Login is denied due to a CAPTCHA requirement, or any other '
             'reason. Please, login (re-login) into Jira via browser '
             'and try again.',
        409: 'Login is denied due to an unverified email. '
             'The email must be verified by logging in to JIRA through a '
             'browser and verifying the email.'
    }

    def __init__(self, status_code, host=None, auth_method=None, credentials=None):
        super(TelegramError, self).__init__()
        self.db = MongoBackend()
        self.message = self.login_error.get(status_code, 'Some problems with login')
        self.host = host
        self.credentials = credentials

        # If handled an error about rejected token and auth method is `oauth`
        if status_code == 401 and auth_method == 'oauth':
            self.host_not_verified()

    def host_not_verified(self):
        # Changing `is_confirmed` flag of the host to False
        # will re-generate a data for the Application link
        self.db.update_host(self.host, {'is_confirmed': False})


class JiraConnectionError(BaseJTBException):
    """Error if jira host does not exist or temporal unavailable"""
    def __init__(self, host):
        super(TelegramError, self).__init__()
        self.message = "Can't connect to Jira host, please check the host status:\n{}".format(host)


class JiraReceivingDataException(BaseJTBException):
    """Any unpredictable errors during receiving data from Jira API"""
    def __init__(self, occurrence, message):
        super(TelegramError, self).__init__()
        self.message = f"Unpredictable error occurred during {occurrence} - {message}"


class JiraInfoException(BaseJTBException):
    """Any predictable informational error during receiving data from JIRA API"""
    pass


class BotAuthError(BaseJTBException):
    """Errors in validating user credentials"""
    pass


class SendMessageHandlerError(BaseJTBException):
    """Error in logic according to sending messages"""
    pass


class DateTimeValidationError(BaseJTBException):
    """Errors in date validation"""
    pass


class DateParsingError(BaseJTBException):
    """Errors in date parsing"""
    pass


class ScheduleValidationError(BaseJTBException):
    """Schedule value validation error"""
    pass


class ContextValidationError(BaseJTBException):
    """Command context validation error"""
    pass


class ArgumentParserError(Exception):
    """Command args parser error"""
    pass
