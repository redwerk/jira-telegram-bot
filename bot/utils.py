from typing import List

from cryptography.fernet import Fernet
from decouple import config


def get_encoder():
    secret = config('SECRET_KEY')
    return Fernet(key=bytes(secret.encode()))


def encrypt_password(password):
    encoder = get_encoder()
    return encoder.encrypt(password.encode())


def decrypt_password(encrypted_password):
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
