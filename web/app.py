import logging
from logging.config import fileConfig

from flask import Flask
from celery import Celery
from decouple import config

from lib.db import MongoBackend

db = MongoBackend()

fileConfig('./logging_config.ini')
logger = logging.getLogger()
logger.handlers[0].fromaddr = config('LOGGER_EMAIL')
logger.handlers[1].toaddrs = [email.strip() for email in config('DEV_EMAILS').split(',')]

# Flask settings
app = Flask(__name__)
app.secret_key = config('SECRET_KEY')

celery = Celery(app.name)
celery.conf.broker_url = config("CELERY_BROKER_URL")

from .auth import auth as auth_blueprint
app.register_blueprint(auth_blueprint, url_prefix='/auth')

from .webhooks import webhooks as webhooks_blueprint
app.register_blueprint(webhooks_blueprint, url_prefix='/webhook')
