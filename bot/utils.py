from typing import List

from cryptography.fernet import Fernet
from decouple import config


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
