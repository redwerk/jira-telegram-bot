import logging
import pymongo
from pymongo.errors import ServerSelectionTimeoutError
from decouple import config


def get_db_connect(func):
    """
    Decorator establishes a connection to the database and checks it. 
    If the connection is - passes the object to the function to execute 
    the query. If you have no connection - writes to the log. 
    In any case closes the connection to the database.
    :param func: unction in which the actions with the DB will be performed
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
    def get_user_credential(self, user_id, *args, **kwargs):
        db = kwargs.get('db')
        user = db.find_one({'telegram_id': user_id})

        if user:
            return user

        return False
