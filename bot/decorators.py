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

        auth = instance.app.get_and_check_cred(telegram_id)
        kwargs.update({'auth_data': auth})
        func(*args, **kwargs)

    return wrapper
