import logging
from datetime import datetime

from decouple import config
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError


class MongoBackend:
    """An interface that contains basic methods for working with the database"""
    collection_mapping = {
        'user': config('DB_USER_COLLECTION'),
        'host': config('DB_HOST_COLLECTION'),
        'cache': config('DB_CACHE_COLLECTION'),
        'webhook': config('DB_WEBHOOK_COLLECTION'),
        'subscriptions': config('DB_SUBSCRIPTIONS_COLLECTION'),
    }

    def __init__(self, user=None, password=None, host=None, port=None, db_name=None):
        self.uri = 'mongodb://{user}:{password}@{host}:{port}'.format(
            user=user or config('DB_USER'),
            password=password or config('DB_PASS'),
            host=host or config('DB_HOST'),
            port=port or config('DB_PORT'),
        )
        self.db_name = db_name or config('DB_NAME')

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

    def _get_collection(self, name: str) -> MongoClient:
        """Returns MongoClient object which links to selected collection"""
        db = self._get_connect()
        return db[self.collection_mapping.get(name)]

    def create_user(self, user_data: dict) -> bool:
        collection = self._get_collection('user')
        status = collection.insert(user_data)

        return True if status else False

    def update_user(self, telegram_id: int, user_data: dict) -> bool:
        """
        Updates the specified fields in user collection
        Matching by: telegram id
        """
        collection = self._get_collection('user')
        status = collection.update({'telegram_id': telegram_id}, {'$set': user_data})

        return True if status else False

    def is_user_exists(self, telegram_id: int) -> bool:
        collection = self._get_collection('user')
        return collection.count({"telegram_id": telegram_id}) > 0

    def get_user_data(self, user_id: int) -> dict:
        collection = self._get_collection('user')
        user = collection.find_one({'telegram_id': user_id})

        if user:
            return user

        return dict()

    def create_host(self, host_data: dict) -> bool:
        collection = self._get_collection('host')
        status = collection.insert(host_data)

        return True if status else False

    def update_host(self, host_url, host_data):
        """
        Updates the specified fields in host collection
        Matching by: host url
        """
        collection = self._get_collection('host')
        status = collection.update({'url': host_url}, {'$set': host_data})

        return True if status else False

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

        return True if status else False

    def get_cached_content(self, key: str) -> dict:
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
