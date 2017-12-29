import os
import logging
import re
import smtplib
import uuid
from email.mime.text import MIMEText
from string import Template

from cryptography.fernet import Fernet
from decouple import config

from bot.exceptions import DateTimeValidationError


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOSTNAME_RE = re.compile(r'^http[s]?://([^:/\s]+)?$')
HTTP_PTOTOCOL = re.compile(r'^http[s]?://')
EMAIL_ADDRESS = re.compile(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')


def encrypt_password(password):
    encoder = Fernet(key=bytes(config('SECRET_KEY').encode()))
    return encoder.encrypt(password.encode())


def decrypt_password(encrypted_password):
    encoder = Fernet(key=bytes(config('SECRET_KEY').encode()))
    password = encoder.decrypt(encrypted_password)
    return password.decode()


def validate_date_range(start_date, end_date):
    """Check that the start date is not older than the end date"""
    if start_date > end_date:
        raise DateTimeValidationError('End date cannot be less than the start date')


def calculate_tracking_time(seconds):
    """Converts time from seconds into hours"""
    hours = 0
    hour_in_seconds = 3600
    try:
        hours = seconds / hour_in_seconds
    except TypeError:
        logging.exception('Seconds are not a numeric type: {} {}'.format(type(seconds), seconds))

    return round(hours, 2)


def read_rsa_key(path):
    """Reads a RSA key"""
    key = None
    try:
        file = open(path, 'r')
        key = file.read()
    except FileNotFoundError as e:
        logging.exception('RSA key did not found by path: {}'.format(path))

    return key


def validates_hostname(url):
    """Validates hostname"""
    return bool(HOSTNAME_RE.match(url))


def generate_consumer_key():
    """Generates a consumer key"""
    return uuid.uuid4().hex


def get_email_address(text):
    """Gets email from the message"""
    email = EMAIL_ADDRESS.findall(text)
    return email[0] if email else False


def get_text_without_email(text):
    """Delete email address from the message"""
    text = EMAIL_ADDRESS.sub('', text)
    return text.strip()


def generate_email_message(sender_email, recipient_email, subject, message):
    """Generates an e-mail for further sending"""
    email_message = MIMEText(message)
    email_message['Subject'] = subject
    email_message['From'] = sender_email or 'root@jirabot.redwer.com'
    email_message['To'] = recipient_email
    return email_message


def send_email(message):
    """Sends a message to the recipient"""
    s = smtplib.SMTP('localhost')
    try:
        s.send_message(message)
    except smtplib.SMTPException as e:
        logging.exception('Error while sending a feedback email: {}'.format(e))
        return False
    else:
        return True
    finally:
        s.quit()


def read_file(filename):
    """Read and return file data."""
    data = None
    with open(os.path.join(BASE_DIR, filename), "rt") as file:
        data = file.read()
    return data


def generate_webhook_url(webhook_id):
    """Generates a Webhook URL for processing updates"""
    host = config('OAUTH_SERVICE_URL')
    return '{0}/webhook/{1}'.format(host, webhook_id) + '/${project.key}/${issue.key}'


def read_template(filepath):
    """Read a text file and return a string.Template object"""
    with open(os.path.join(BASE_DIR, filepath)) as file:
        template = Template(file.read())
    return template


def filters_subscribers(subscribers, project, issue=None):
    """
    Filtering subscribers through its topics: project or issue
    :param subscribers: list of user subscribers info in dictionary type
    :param project: project key e.g. JTB
    :param issue: issue key e.g. JTB-99
    :return: set of chat_ids
    """
    sub_users = list()

    for sub in subscribers:
        sub_topic = sub.get('topic')
        sub_name = sub.get('name')
        sub_chat_id = sub.get('chat_id')
        project_cond = sub_topic == 'project' and project == sub_name

        if project:
            if sub_topic == 'project' and project == sub_name:
                sub_users.append(sub_chat_id)
        if issue:
            if sub_topic == 'issue' and issue == sub_name or project_cond:
                sub_users.append(sub_chat_id)

    return set(sub_users)
