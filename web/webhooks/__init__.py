from flask import Blueprint

webhooks = Blueprint('webhooks', __name__)

from . import views # noqa
