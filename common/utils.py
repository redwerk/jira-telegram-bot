import logging
import re
import smtplib
import uuid
from email.mime.text import MIMEText
from typing import List

from cryptography.fernet import Fernet
from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from common.exceptions import DateTimeValidationError

hostname_re = re.compile(r'^http[s]?://([^:/\s]+)?$')
http_ptotocol = re.compile(r'^http[s]?://')
email_address = re.compile(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')


def encrypt_password(password):
    encoder = Fernet(key=bytes(config('SECRET_KEY').encode()))
    return encoder.encrypt(password.encode())


def decrypt_password(encrypted_password):
    encoder = Fernet(key=bytes(config('SECRET_KEY').encode()))
    password = encoder.decrypt(encrypted_password)

    return password.decode()


def build_menu(buttons: List,
               n_cols: int,
               header_buttons: List = None,
               footer_buttons: List = None) -> List:
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]

    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)

    return menu


def split_by_pages(issues: list, item_per_page: int) -> list:
    """
    Return list of lists. Each list contains elements associated to
    page number + 1.

    exp: issues = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    items_by_pages = split_by_pages(issues, 3) # 3 items per page
    items_by_pages # [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]

    page = 4 # want to get items from page 4
    items_by_pages[page + 1] # [10]

    :param issues: list of items
    :param item_per_page: count of items per page
    :return: list of lists
    """
    splitted_issues = list()

    for start in range(0, len(issues), item_per_page):
        splitted_issues.append(issues[start:start + item_per_page])

    return splitted_issues


def get_pagination_keyboard(current: int,
                            max_page: int,
                            str_key: str) -> InlineKeyboardMarkup:
    """
    Generating an inline keyboard for displaying pagination
    :param current: selected page number
    :param max_page: max page number for displaying in keyboard
    :param str_key: some key for different handlers
    :return: list from formed inline buttons
    """
    inline_buttons = []

    if current > 1:
        inline_buttons.append(
            InlineKeyboardButton(
                '« 1',
                callback_data=str_key.format('1')
            )
        )

    if current > 2:
        inline_buttons.append(
            InlineKeyboardButton(
                '< {}'.format(current - 1),
                callback_data=str_key.format(current - 1)
            )
        )

    inline_buttons.append(
        InlineKeyboardButton(
            '· {} ·'.format(current),
            callback_data=str_key.format(current)
        )
    )

    if current < max_page - 1:
        inline_buttons.append(
            InlineKeyboardButton(
                '{} >'.format(current + 1),
                callback_data=str_key.format(current + 1)
            )
        )

    if current < max_page:
        inline_buttons.append(
            InlineKeyboardButton(
                '{} »'.format(max_page),
                callback_data=str_key.format(max_page)
            )
        )

    return InlineKeyboardMarkup(build_menu(
        inline_buttons, n_cols=len(inline_buttons)
    ))


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


def validates_hostname(url: str) -> bool:
    """Validates hostname"""
    return True if hostname_re.match(url) else False


def generate_consumer_key() -> str:
    """Generates a consumer key"""
    return uuid.uuid4().hex


def get_email_address(text):
    """Gets email from the message"""
    email = email_address.findall(text)
    return email[0] if email else False


def get_text_without_email(text):
    """Delete email address from the message"""
    text = email_address.sub('', text)
    return text.strip()


def generate_email_message(sender_email, recipient_email, subject, message):
    """Generates an e-mail for further sending"""
    email_message = MIMEText(message)
    email_message['Subject'] = subject
    email_message['From'] = sender_email if sender_email else 'root@jirabot.redwer.com'
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


def login_required(func):
    """
    Decorator for commands: to check the availability and relevance of user credentials
    If the checks are successful, then there is no need to repeatedly request the user's credentials -
    they will be added to the `kwargs`
    """
    def wrapper(*args, **kwargs):
        try:
            instance, bot, update = args
        except IndexError as e:
            logging.exception('login_required decorator: {}'.format(e))
            return

        try:
            # update came from CommandHandler (after execute /command)
            telegram_id = update.message.chat_id
        except AttributeError:
            # update came from CallbackQueryHandler (after press button on inline keyboard)
            telegram_id = update.callback_query.from_user.id

        user_exists = instance._bot_instance.db.is_user_exists(telegram_id)

        if not user_exists:
            bot.send_message(
                chat_id=telegram_id,
                text='You are not in the database. Just call the /start command',
            )
            return

        auth = instance._bot_instance.get_and_check_cred(telegram_id)
        kwargs.update({'auth_data': auth})
        func(*args, **kwargs)

    return wrapper


def generate_webhook_url(webhook_id):
    host = config('OAUTH_SERVICE_URL')
    return '{0}/webhook/{1}'.format(host, webhook_id) + '/${project.key}/${issue.key}'
