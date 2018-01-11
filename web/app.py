import logging

from flask import Flask
from celery import Celery
from decouple import config

from lib.db import MongoBackend

db = MongoBackend()
logger = logging.getLogger()

# Flask settings
app = Flask(__name__)
app.secret_key = config('SECRET_KEY')

celery = Celery(app.name)
celery.conf.broker_url = config("CELERY_BROKER_URL")

from .auth import auth as auth_blueprint
app.register_blueprint(auth_blueprint, url_prefix='/auth')

from .webhooks import webhooks as webhooks_blueprint
app.register_blueprint(webhooks_blueprint, url_prefix='/webhook')
