import calendar
import logging
from datetime import datetime
from typing import Generator, List

import pytz
from cryptography.fernet import Fernet
from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_encoder() -> Fernet:
    secret = config('SECRET_KEY')
    return Fernet(key=bytes(secret.encode()))


def encrypt_password(password: str) -> bytes:
    encoder = get_encoder()
    return encoder.encrypt(password.encode())


def decrypt_password(encrypted_password: bytes) -> str:
    encoder = get_encoder()
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


def create_calendar(year: int,
                    month: int,
                    pattern_key: str) -> InlineKeyboardMarkup:
    buttons = list()
    previous_m = 'change_m:{}.{}'.format(month - 1, year)
    next_m = 'change_m:{}.{}'.format(month + 1, year)

    week_days = ['M', 'T', 'W', 'R', 'F', 'S', 'U']
    for week_day in week_days:
        buttons.append(
            InlineKeyboardButton(
                week_day, callback_data='ignore'
            )
        )

    h_buttons = [
        InlineKeyboardButton(
            calendar.month_name[month] + ' ' + str(year),
            callback_data='ignore'
        )
    ]
    f_buttons = [
        InlineKeyboardButton(
            '< ' + calendar.month_name[month - 1],
            callback_data=pattern_key.format(previous_m)
        ),
        InlineKeyboardButton(
            ' ', callback_data='ignore'
        ),
        InlineKeyboardButton(
            calendar.month_name[month + 1] + ' >',
            callback_data=pattern_key.format(next_m)
        )
    ]

    current_month = calendar.monthcalendar(year, month)
    for week in current_month:
        for day in week:
            if day:
                date = '{}-{}-{}'.format(year, month, day)
                buttons.append(
                    InlineKeyboardButton(
                        str(day),
                        callback_data=pattern_key.format(date)
                    )
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


def read_private_key(path):
    """Read private RSA key for requests via OAuth"""
    key_cert = None

    try:
        file = open(path, 'r')
        key_cert = file.read()
    except FileNotFoundError as e:
        logging.warning('RSA private key did not found by path: {}'.format(path))

    return key_cert
