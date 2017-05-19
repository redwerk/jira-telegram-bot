import logging

from bson import ObjectId
from decouple import config
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, WriteError


def mongodb_connect(func):
    """
    Decorator establishes a connection to the database and checks it. 
    If the connection is - passes the object to the function to execute 
    the query. If you have no connection - writes to the log. 
    In any case closes the connection to the database.
    :param func: function in which the actions with the DB will be performed
    :return: data from DB
    """
    def wrapper(*args, **kwargs):
        db_name = config('DB_NAME')
        collection = config('DB_COLLECTION')
        data = False

        client = MongoClient(
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

    @staticmethod
    def create_user(user_data: dict, db: MongoClient):
        db.insert_one(user_data)

    @staticmethod
    def update_user(user_id: ObjectId, user_data: dict, db: MongoClient):
        db.update({'_id': user_id}, user_data)

    @staticmethod
    def get_user_data(user_id: str, db: MongoClient) -> dict:
        user = db.find_one({'telegram_id': user_id})

        if user:
            return user

        return dict()

    @mongodb_connect
    def save_credentials(self, user_data: dict, *args, **kwargs) -> bool:
        """
        If the user is in the database - updates the data. 
        If not - creates a user in the database.
        :param user_data: user credentials in dict
        :param args: 
        :param kwargs: contains objects database access
        :return: status of the transaction
        """
        db = kwargs.get('db')

        user = self.get_user_data(
            user_data.get('telegram_id'),
            db
        )

        if user:
            user_id = user.get('_id')
            try:
                self.update_user(user_id, user_data, db)
            except WriteError as e:
                logging.warning('Error updating user: {}'.format(e))
                return False
            else:
                logging.info(
                    'Credentials of {} was '
                    'updated'.format(user_data['jira']['username'])
                )
                return True
        else:
            try:
                self.create_user(user_data, db)
            except WriteError as e:
                logging.warning('Error creating user: {}'.format(e))
                return False
            else:
                logging.info(
                    'User {} was created '
                    'successfully'.format(user_data.get('username', ''))
                )
                return True

    @mongodb_connect
    def get_user_credentials(self, telegram_id: str, *args, **kwargs) -> dict:
        db = kwargs.get('db')

        user = self.get_user_data(telegram_id, db)

        if user:
            username = user['jira']['username']
            password = user['jira']['password']
            return dict(username=username, password=password)

        return dict()
