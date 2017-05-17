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
