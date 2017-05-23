from typing import List

from cryptography.fernet import Fernet
from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_encoder():
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
               footer_buttons: List = None):
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
    def slice_generator(sequence, item_per_page):
        for start in range(0, len(sequence), item_per_page):
            yield sequence[start:start + item_per_page]

    return list(slice_generator(issues, item_per_page))


def get_pagination_keyboard(current: int, max_page: int, str_key: str):
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
                '<< 1',
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
                '{} >>'.format(max_page),
                callback_data=str_key.format(max_page)
            )
        )

    return InlineKeyboardMarkup(build_menu(
        inline_buttons, n_cols=len(inline_buttons)
    ))
