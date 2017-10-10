import logging
from datetime import datetime

from decouple import config
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, WriteError


class MongoBackend:
    """An interface that contains basic methods for working with the database"""
    collection_mapping = {
        'user': config('DB_USER_COLLECTION'),
        'host': config('DB_HOST_COLLECTION'),
        'cache': config('DB_CACHE_COLLECTION'),
    }

    def __init__(self, user, password, host, port, db_name):
        self.uri = 'mongodb://{user}:{password}@{host}:{port}/{db_name}'.format(
            user=user,
            password=password,
            host=host,
            port=port,
            db_name=db_name
        )
        self.db_name = db_name

    def _get_connect(self):
        """
        Creates and checks connect to MongoDB
        :return MongoClient object to db_name
        """
        client = MongoClient(self.uri, serverSelectionTimeoutMS=1)

        try:
            client.server_info()  # checking a connection to DB
        except (ServerSelectionTimeoutError, OperationFailure) as error:
            logging.exception("Can't connect to DB: {}".format(error))
        else:
            return client[self.db_name]

    def _get_collection(self, name: str, kwargs: dict) -> MongoClient:
        """Returns MongoClient object which links to selected collection"""
        db = self._get_connect()
        return db[self.collection_mapping.get(name)]

    def create_user(self, user_data: dict, **kwargs) -> bool:
        collection = self._get_collection('user', kwargs)
        status = collection.insert(user_data)

        return True if status else False

    def update_user(self, telegram_id: int, user_data: dict, **kwargs) -> bool:
        """
        Updates the specified fields in user collection
        Matching by: telegram id
        """
        collection = self._get_collection('user', kwargs)
        status = collection.update({'telegram_id': telegram_id}, {'$set': user_data})

        return True if status else False

    def is_user_exists(self, telegram_id: int, **kwargs) -> bool:
        collection = self._get_collection('user', kwargs)
        return collection.count({"telegram_id": telegram_id}) > 0

    def get_user_data(self, user_id: int, **kwargs) -> dict:
        collection = self._get_collection('user', kwargs)
        user = collection.find_one({'telegram_id': user_id})

        if user:
            return user

        return dict()

    def create_host(self, host_data: dict, **kwargs) -> bool:
        collection = self._get_collection('host', kwargs)
        status = collection.insert(host_data)

        return True if status else False

    def update_host(self, host_url, host_data, **kwargs):
        """
        Updates the specified fields in host collection
        Matching by: host url
        """
        collection = self._get_collection('host', kwargs)
        status = collection.update({'url': host_url}, {'$set': host_data})

        return True if status else False

    def get_host_data(self, url, **kwargs):
        """Returns host data according to host URL"""
        collection = self._get_collection('host', kwargs)
        host = collection.find_one({'url': url})

        return host

    def search_host(self, host, **kwargs):
        """Search a host in DB by pattern matching"""
        collection = self._get_collection('host', kwargs)
        host = collection.find_one({'url': {'$regex': 'http(s)?://' + host}})
        return host

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

    def get_cached_content(self, key: str, **kwargs) -> dict:
        """Gets document from cache collection"""
        collection = self._get_collection('cache', kwargs)
        document = collection.find_one({'key': key})

        if document:
            return dict(content=document.get('content'), page_count=document.get('page_count'))

        return dict()
