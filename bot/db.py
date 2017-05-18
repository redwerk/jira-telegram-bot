import logging

import pymongo
from decouple import config
from pymongo.errors import ServerSelectionTimeoutError


def get_db_connect(func):
    """
    Decorator establishes a connection to the database and checks it. 
    If the connection is - passes the object to the function to execute 
    the query. If you have no connection - writes to the log. 
    In any case closes the connection to the database.
    :param func: function in which the actions with the DB will be performed
    :return: 
    """
    def wrapper(*args, **kwargs):
        db_name = config('DB_NAME')
        collection = config('DB_COLLECTION')
        data = False

        client = pymongo.MongoClient(
            host=config('DB_HOST'),
            port=config('DB_PORT', cast=int),
            serverSelectionTimeoutMS=1
        )

        try:
            client.server_info()  # checking a connection to DB
        except ServerSelectionTimeoutError as error:
            logging.error("Can't connect to DB: {}".format(error))
        else:
            db = client[db_name][collection]
            kwargs.update({'db': db})
            data = func(*args, **kwargs)
        finally:
            client.close()

        return data

    return wrapper


class MongoBackend(object):
    """An interface that contains basic methods for working with the database"""

    @get_db_connect
    def create_user(self, user_data, *args, **kwargs):
        db = kwargs.get('db')
        db.insert_one(user_data)

    @get_db_connect
    def get_user_data(self, user_id, *args, **kwargs):
        db = kwargs.get('db')
        user = db.find_one({'telegram_id': user_id})

        if user:
            return user

        return False

    @get_db_connect
    def update_user_credential(self, user_data, *args, **kwargs):
        pass
