import logging

def connect_required(func):
    """
    Decorator for commands: to check the availability and connect of user.
    If the checks are successful, users chat_id appended to list of listeners.
    """
    def wrapper(*args, **kwargs):
        try:
            self, update, chat_ids, host, db, *other_args = args
        except IndexError as e:
            logging.exception('connect_required decorator: {}'.format(e))
            func(*args, **kwargs)
            return

        filtered_chat_ids = []

        for chat_id in chat_ids:
            # do not proceed any actions for disconnected user
            if not db.is_user_connected(chat_id):
                logging.debug('connect_required decorator: User disconnected')
            else:
                filtered_chat_ids.append(chat_id)

        func(self, update, filtered_chat_ids, host, db, *other_args, **kwargs)

    return wrapper
