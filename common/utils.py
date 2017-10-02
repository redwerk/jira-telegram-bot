import calendar
import logging
import re
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Generator, List

import pendulum
import pytz
from cryptography.fernet import Fernet
from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .errors import BotAuthError, JiraConnectionError, JiraLoginError

hostname_re = re.compile(r'^http[s]?://([^:/\s]+)?$')
http_ptotocol = re.compile(r'^http[s]?://')
email_address = re.compile(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')

JIRA_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
USER_DATE_FORMAT = '%Y-%m-%d'


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

    def slice_generator(sequence: list, item_per_page: int) -> Generator:
        for start in range(0, len(sequence), item_per_page):
            yield sequence[start:start + item_per_page]

    return list(slice_generator(issues, item_per_page))


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


def create_calendar(date: pendulum.Pendulum, pattern_key: str, selected_day=None) -> InlineKeyboardMarkup:
    buttons = list()

    # for the month change buttons
    last_month = date.subtract(months=1)
    next_month = date.add(months=1)

    previous_m = 'change_m:{}.{}'.format(last_month.month, last_month.year)
    next_m = 'change_m:{}.{}'.format(next_month.month, next_month.year)

    # to select a time interval with a single button
    now_obj = pendulum.now()
    today = '{0}:{0}'.format(now_obj.date())
    current_month = '{}:{}'.format(
        now_obj._start_of_month().date(),
        now_obj._end_of_month().date()
    )
    displayed_month = '{}:{}'.format(
        date._start_of_month().date(),
        date._end_of_month().date()
    )

    week_days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
    for week_day in week_days:
        buttons.append(
            InlineKeyboardButton(
                week_day, callback_data='ignore'
            )
        )

    h_buttons = [
        InlineKeyboardButton(
            calendar.month_name[date.month] + ' ' + str(date.year),
            callback_data=pattern_key.format(displayed_month)
        ),
        InlineKeyboardButton(
            'Today',
            callback_data=pattern_key.format(today)
        ),
        InlineKeyboardButton(
            'Current month',
            callback_data=pattern_key.format(current_month)
        ),
    ]
    f_buttons = [
        InlineKeyboardButton(
            '< ' + calendar.month_name[last_month.month],
            callback_data=pattern_key.format(previous_m)
        ),
        InlineKeyboardButton(
            '« Back', callback_data='tracking_menu'
        ),
        InlineKeyboardButton(
            calendar.month_name[next_month.month] + ' >',
            callback_data=pattern_key.format(next_m)
        )
    ]

    current_month = calendar.monthcalendar(date.year, date.month)
    for week in current_month:
        for day in week:
            if day:
                _day = pendulum.create(date.year, date.month, day)
                tmp_date = '{}-{}-{}'.format(_day.year, _day.month, _day.day)
                title = str(day)

                # visually mark the date
                if selected_day and not _day.diff(selected_day).days:
                    title = '·{}·'.format(title)

                buttons.append(
                    InlineKeyboardButton(title, callback_data=pattern_key.format(tmp_date))
                )
            else:
                buttons.append(
                    InlineKeyboardButton(' ', callback_data='ignore')
                )

    return InlineKeyboardMarkup(
        build_menu(
            buttons,
            n_cols=7,
            header_buttons=h_buttons,
            footer_buttons=f_buttons
        )
    )


def to_datetime(_time: str, _format: str) -> (datetime or bool):
    """
    Converts dates to a datetime object. If necessary, add an attribute tzinfo
    :param _time: '2017-05-25'
    :param _format: '%Y-%m-%d'
    :return: datetime object or False
    """
    try:
        dt = datetime.strptime(_time, _format)
    except (TypeError, ValueError) as e:
        logging.exception(
            'Date conversion error: {}'.format(e)
        )
    else:
        if not getattr(dt, 'tzinfo'):
            return dt.replace(tzinfo=pytz.UTC)
        return dt

    return False


def add_time(date: datetime, hours=0, minutes=0) -> datetime:
    """Adds time (hours and minutes) to datetime object"""
    additional_time = timedelta(hours=hours, minutes=minutes)

    try:
        date += additional_time
    except TypeError as e:
        logging.exception(e)

    return date


def to_human_date(_time: datetime) -> str:
    """
    Represent date in human readable format
    :param _time: datetime object
    :return: 2017-06-06 16:45
    """
    try:
        return _time.strftime('%Y-%m-%d %H:%M')
    except AttributeError as e:
        logging.exception("Can't parse entered date: {}, {}".format(_time, e))

    return 'No date'


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
    """
    Validates hostname by next patterns:

    https://jira.redwerk.com                 True
    https://jira.test.redwerk.com            True
    https://jira.test.redwerk.com/           False
    test                                     False
    www.test.com                             False
    http//test.com                           False
    https//test.com                          False
    https://test.com                         True
    """
    return True if hostname_re.match(url) else False


def generate_consumer_key() -> str:
    """Generates a consumer key"""
    return uuid.uuid4().hex


def generate_key_name(host_url: str) -> str:
    """Generates a name for private key from host name"""
    name = http_ptotocol.sub('', host_url)
    return '{}_key.pem'.format(name.replace('.', '_'))


def generate_readable_name(host_url: str) -> str:
    """Generates a readable name for Jira host in DB"""
    name = http_ptotocol.sub('', host_url)
    name_list = name.replace('.com', '').split('.')

    return ' '.join([word[0].upper() + word[1:] for word in name_list])


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

        telegram_id = update.message.chat_id
        user_exists = instance._bot_instance.db.is_user_exists(telegram_id)

        if not user_exists:
            bot.send_message(
                chat_id=telegram_id,
                text='You are not in the database. Just call the /start command',
            )
            return

        try:
            auth = instance._bot_instance.get_and_check_cred(telegram_id)
        except (JiraLoginError, JiraConnectionError, BotAuthError) as e:
            bot.send_message(chat_id=telegram_id, text=e.message)
            return
        else:
            kwargs.update({'auth_data': auth})
            func(*args, **kwargs)

    return wrapper
