import logging

from flask import Flask
from celery import Celery
from celery.signals import after_setup_logger
from decouple import config

from lib.db import MongoBackend

import logger

db = MongoBackend()

# Flask settings
app = Flask(__name__)
app.secret_key = config('SECRET_KEY')

logger = logger.logger

celery = Celery(app.name)
celery.conf.broker_url = config("CELERY_BROKER_URL")

from .auth import auth as auth_blueprint
app.register_blueprint(auth_blueprint, url_prefix='/auth')

from .webhooks import webhooks as webhooks_blueprint
app.register_blueprint(webhooks_blueprint, url_prefix='/webhook')


@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    """
    Additional configuration for Celery
    The only way to add/change handlers for Celery logging
    :param logger: root logger of Celery
    :param args:
    :param kwargs:
    :return:
    """
    formatter = logging.Formatter('[%(asctime)s: %(levelname)s] %(name)s: %(message)s')

    file_handler = logging.FileHandler('logs/celery.log')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
