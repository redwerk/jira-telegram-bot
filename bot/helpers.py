import logging


def login_required(func):
    """
    Decorator for commands: to check the availability and relevance
    of user credentials. If the checks are successful, then there is
    no need to repeatedly request the user's credentials - they will
    be added to the `kwargs`.
    """
    def wrapper(*args, **kwargs):
        try:
            instance, bot, update, *_ = args
        except IndexError as e:
            logging.exception('login_required decorator: {}'.format(e))
            return

        try:
            # update came from CommandHandler (after execute /command)
            telegram_id = update.message.chat_id
        except AttributeError:
            # update came from CallbackQueryHandler (after press button on inline keyboard)
            telegram_id = update.callback_query.from_user.id

        if not instance.app.db.is_user_exists(telegram_id):
            bot.send_message(
                chat_id=telegram_id,
                text='You are not in the database. Just call the /start command',
            )
            return

        auth = instance.app.authorization(telegram_id)
        kwargs.update({'auth_data': auth})
        func(*args, **kwargs)

    return wrapper


def get_query_scope(update):
    """
    Gets scope data for current message
    TODO: make refactoring in the future
    """
    telegram_id = update.callback_query.from_user.id
    query = update.callback_query
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    data = query.data
    return dict(
        telegram_id=telegram_id,
        chat_id=chat_id,
        message_id=message_id,
        data=data
    )


class Singleton(type):
    """Singleton metaclass"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
