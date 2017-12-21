from datetime import datetime
import sys
import logging

from bson.objectid import ObjectId
from decouple import config
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError


def create_connection(**kwargs):
    """
    Creates and checks connect to MongoDB.

    Kwargs:
        user (str): database username
        password (str): user password
        host (str): database host location
        port (int): database port
        db_name (str): database name

    Returns:
        pymongo.MongoClient: connection to db_name
    """
    user = kwargs.get("user", config('DB_USER'))
    password = kwargs.get("password", config('DB_PASS'))
    host = kwargs.get("host", config('DB_HOST'))
    port = kwargs.get("port", config('DB_PORT'))

    if user and password:
        uri = f'mongodb://{user}:{password}@{host}:{port}'
    else:
        uri = f'mongodb://{host}:{port}'

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=1)
        client.server_info()  # checking a connection to DB
    except (ServerSelectionTimeoutError, OperationFailure) as err:
        logging.exception("Can't connect to DB: {}".format(err))
        sys.exit(1)

    return client[kwargs.get("db_name", config('DB_NAME'))]


class MongoBackend:
    """An interface that contains basic methods for working with the database.

    Keyword arguments:
        conn (pymongo.MongoClient): connection to database
        user (str): database username
        password (str): user password
        host (str): database host location
        port (int): database port
        db_name (str): database name
    """
    collection_mapping = {
        'user': config('DB_USER_COLLECTION'),
        'host': config('DB_HOST_COLLECTION'),
        'cache': config('DB_CACHE_COLLECTION'),
        'webhook': config('DB_WEBHOOK_COLLECTION'),
        'subscriptions': config('DB_SUBSCRIPTIONS_COLLECTION'),
        'schedule': config("SCHEDULE_COLLECTION", "schedules"),
    }

    def __init__(self, conn=None, **kwargs):
        if conn is None:
            self._conn = create_connection(**kwargs)
        else:
            self._conn = conn

    @property
    def conn(self):
        return self._conn

    def _get_collection(self, name: str) -> MongoClient:
        """Returns MongoClient object which links to selected collection"""
        return self._conn[self.collection_mapping.get(name)]

    def create_user(self, user_data):
        collection = self._get_collection('user')
        status = collection.insert(user_data)
        return bool(status)

    def update_user(self, telegram_id, user_data):
        """
        Updates the specified fields in user collection
        Matching by: telegram id
        """
        collection = self._get_collection('user')
        status = collection.update({'telegram_id': telegram_id}, {'$set': user_data})
        return bool(status)

    def is_user_exists(self, telegram_id):
        collection = self._get_collection('user')
        return collection.count({"telegram_id": telegram_id}) > 0

    def get_user_data(self, user_id):
        collection = self._get_collection('user')
        user = collection.find_one({'telegram_id': user_id})
        return user or dict()

    def create_host(self, host_data):
        collection = self._get_collection('host')
        status = collection.insert(host_data)
        return bool(status)

    def update_host(self, host_url, host_data):
        """
        Updates the specified fields in host collection
        Matching by: host url
        """
        collection = self._get_collection('host')
        status = collection.update({'url': host_url}, {'$set': host_data})
        return bool(status)

    def get_host_data(self, url):
        """Returns host data according to host URL"""
        collection = self._get_collection('host')
        host = collection.find_one({'url': url})
        return host

    def search_host(self, host):
        """Search a host in DB by pattern matching"""
        collection = self._get_collection('host')
        host = collection.find_one({'url': {'$regex': 'http(s)?://' + host}})
        return host

    def create_cache(self, key, title, content, page_count):
        """
        Creates a document for content which has the ability to paginate
        Documents will delete by MongoDB when they will expire
        """
        collection = self._get_collection('cache')
        status = collection.insert_one(
            {
                'key': key,
                'title': title,
                'content': content,
                'page_count': page_count,
                'createdAt': datetime.utcnow(),
            }
        )
        return bool(status)

    def get_cached_content(self, key):
        """Gets document from cache collection"""
        collection = self._get_collection('cache')
        document = collection.find_one({'key': key})
        if document:
            return {
                'title': document.get('title'),
                'content': document.get('content'),
                'page_count': document.get('page_count')
            }

        return dict()

    def create_webhook(self, key, host):
        collection = self._get_collection('webhook')
        status = collection.insert_one(
            {
                'webhook_id': key,
                'host_url': host,
            }
        )

        return True if status else False

    def update_webhook(self, host, data):
        collection = self._get_collection('webhook')
        status = collection.update({'host_url': host}, {'$set': data})

        return True if status else False

    def get_webhook(self, key):
        collection = self._get_collection('webhook')
        webhook = collection.find_one({'webhook_id': key})

        return webhook if webhook else False

    def search_webhook(self, host):
        collection = self._get_collection('webhook')
        webhook = collection.find_one({'host_url': host})

        return webhook if webhook else False

    def create_subscription(self, data):
        collection = self._get_collection('subscriptions')
        status = collection.insert_one(data)

        return True if status else False

    def get_subscription(self, sub_id):
        collection = self._get_collection('subscriptions')
        subscription = collection.find_one({'sub_id': sub_id})

        return subscription if subscription else False

    def get_webhook_subscriptions(self, webhook_id):
        collection = self._get_collection('subscriptions')
        subs = collection.find({'webhook_id': webhook_id})
        return list(subs) if subs else list()

    def get_user_subscriptions(self, user_id):
        collection = self._get_collection('subscriptions')
        subs = collection.find({'user_id': user_id})
        return list(subs) if subs else list()

    def delete_subscription(self, sub_id):
        collection = self._get_collection('subscriptions')
        status = collection.remove({'sub_id': sub_id})

        return True if status else False

    def delete_all_subscription(self, user_id):
        collection = self._get_collection('subscriptions')
        status = collection.remove({'user_id': user_id})

        return True if status else False
    def get_schedule_commands(self, user_id):
        """Return list of schedules entries.

        Args:
            user_id (int): telegram user id
        Returns:
            (pymongo.cursor.Cursor): found items collection
        """
        collection = self._get_collection('schedule')
        result = collection.find({'user_id': user_id})
        return result

    def remove_schedule_command(self, entry_id):
        """Remove schedule entry by id.

        Args:
            entry_id (str): entry id value
        Returns:
            (int): deleted items count
        """
        collection = self._get_collection('schedule')
        result = collection.delete_one({"_id": ObjectId(entry_id)})
        return result.deleted_count
