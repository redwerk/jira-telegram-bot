import logging

from decouple import config
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, WriteError


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
        data = False
        uri = 'mongodb://{user}:{password}@{host}:{port}/{db_name}'.format(
            user=config('DB_USER'), password=config('DB_PASS'), host=config('DB_HOST'),
            port=config('DB_PORT'), db_name=db_name
        )

        client = MongoClient(uri, serverSelectionTimeoutMS=1)

        try:
            client.server_info()  # checking a connection to DB
        except (ServerSelectionTimeoutError, OperationFailure) as error:
            logging.error("Can't connect to DB: {}".format(error))
        else:
            db = client[db_name]
            kwargs.update({'db': db})
            try:
                data = func(*args, **kwargs)
            except WriteError as e:
                logging.exception('Error while writing to database: {}'.format(e))
        finally:
            client.close()

        return data

    return wrapper


class MongoBackend:
    """An interface that contains basic methods for working with the database"""
    user_collection = config('DB_USER_COLLECTION')
    host_collection = config('DB_HOST_COLLECTION')

    def get_user_collection(self, kwargs: dict) -> MongoClient:
        """Returns MongoClient object which links to user collection"""
        db = kwargs.get('db')
        return db[self.user_collection]

    def get_host_collection(self, kwargs: dict) -> MongoClient:
        """Returns MongoClient object which links to host collection"""
        db = kwargs.get('db')
        return db[self.host_collection]

    @mongodb_connect
    def create_user(self, user_data: dict, **kwargs) -> bool:
        collection = self.get_user_collection(kwargs)
        status = collection.insert(user_data)

        return True if status else False

    @mongodb_connect
    def update_user(self, telegram_id: str, user_data: dict, **kwargs) -> bool:
        """
        Updates only the specified fields.
        Can update the embedded fields like: '0.base.password'
        """
        collection = self.get_user_collection(kwargs)
        status = collection.update({'telegram_id': telegram_id}, {'$set': user_data})

        return True if status else False

    @mongodb_connect
    def is_user_exists(self, telegram_id: str, **kwargs) -> bool:
        collection = self.get_user_collection(kwargs)
        return collection.count({"telegram_id": telegram_id}) > 0

    @staticmethod
    def get_user_data(user_id: str, db: MongoClient) -> dict:
        user = db.find_one({'telegram_id': user_id})

        if user:
            return user

        return dict()

    @mongodb_connect
    def get_user_credentials(self, telegram_id: str, *args, **kwargs) -> dict:
        db = kwargs.get('db')

        user = self.get_user_data(telegram_id, db)

        if user:
            username = user['jira']['username']
            password = user['jira']['password']
            return dict(username=username, password=password)

        return dict()

    @mongodb_connect
    def get_host_id(self, url, **kwargs):
        """Returns host id according to host URL"""
        collection = self.get_host_collection(kwargs)
        host = collection.find_one({'url': url})

        if host:
            return host['id']

        return False
