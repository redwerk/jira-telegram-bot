import logging
from datetime import datetime

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
    collection_mapping = {
        'user': config('DB_USER_COLLECTION'),
        'host': config('DB_HOST_COLLECTION'),
        'cache': config('DB_CACHE_COLLECTION'),
    }

    def _get_collection(self, name: str, kwargs: dict) -> MongoClient:
        """Returns MongoClient object which links to selected collection"""
        db = kwargs.get('db')
        return db[self.collection_mapping.get(name)]

    @mongodb_connect
    def create_user(self, user_data: dict, **kwargs) -> bool:
        collection = self._get_collection('user', kwargs)
        status = collection.insert(user_data)

        return True if status else False

    @mongodb_connect
    def update_user(self, telegram_id: int, user_data: dict, **kwargs) -> bool:
        """
        Updates the specified fields in user collection
        Matching by: telegram id
        """
        collection = self._get_collection('user', kwargs)
        status = collection.update({'telegram_id': telegram_id}, {'$set': user_data})

        return True if status else False

    @mongodb_connect
    def update_host(self, url: str, host_data: dict, **kwargs) -> bool:
        """
        Updates the specified fields in host collection
        Matching by: host url
        """
        collection = self._get_collection('host', kwargs)
        status = collection.update({'url': url}, {'$set': host_data})

        return True if status else False

    @mongodb_connect
    def is_user_exists(self, telegram_id: int, **kwargs) -> bool:
        collection = self._get_collection('user', kwargs)
        return collection.count({"telegram_id": telegram_id}) > 0

    @mongodb_connect
    def get_user_data(self, user_id: int, **kwargs) -> dict:
        collection = self._get_collection('user', kwargs)
        user = collection.find_one({'telegram_id': user_id})

        if user:
            return user

        return dict()

    @mongodb_connect
    def get_user_credentials(self, telegram_id: int, *args, **kwargs) -> dict:
        """Returns data for OAuth authorization and further processing"""
        user = self.get_user_data(telegram_id)
        host = None

        if user:
            host = self.get_host_data(user.get('host_url'))

        if user and host:
            return {
                'username': user['username'],
                'url': host['url'],
                'access_token': user['access_token'],
                'access_token_secret': user['access_token_secret'],
                'consumer_key': host['consumer_key'],
            }

        return dict()

    @mongodb_connect
    def create_host(self, host_data: dict, **kwargs) -> bool:
        collection = self._get_collection('host', kwargs)
        status = collection.insert(host_data)

        return True if status else False

    @mongodb_connect
    def get_host_data(self, url, **kwargs):
        """Returns host data according to host URL"""
        collection = self._get_collection('host', kwargs)
        host = collection.find_one({'url': url})

        return host

    @mongodb_connect
    def search_host(self, host, **kwargs):
        """Search a host in DB by pattern matching"""
        collection = self._get_collection('host', kwargs)
        host = collection.find_one({'url': {'$regex': 'http(s)://' + host}})
        return host

    @mongodb_connect
    def get_hosts(self, ids_list: list, **kwargs):
        """
        Returns matched hosts
        Matching by: ObjectId
        """
        collection = self._get_collection('host', kwargs)
        hosts = collection.find({'_id': {'$in': ids_list}})

        return hosts

    @mongodb_connect
    def create_cache(self, key: str, content: list, page_count: int, **kwargs) -> bool:
        """
        Creates a document for content which has the ability to paginate
        Documents will delete by MongoDB when they will expire
        """
        collection = self._get_collection('cache', kwargs)
        status = collection.insert_one(
            {
                'key': key,
                'content': content,
                'page_count': page_count,
                'createdAt': datetime.utcnow(),
            }
        )

        return True if status else False

    @mongodb_connect
    def get_cached_content(self, key: str, **kwargs) -> dict:
        """Gets document from cache collection"""
        collection = self._get_collection('cache', kwargs)
        document = collection.find_one({'key': key})

        if document:
            return dict(content=document.get('content'), page_count=document.get('page_count'))

        return dict()
