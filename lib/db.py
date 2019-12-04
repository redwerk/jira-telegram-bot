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
    user = kwargs.get("user", config('DB_USER', default=None))
    password = kwargs.get("password", config('DB_PASS', default=None))
    name = kwargs.get("db_name", config('DB_NAME'))
    host = kwargs.get("host", config('DB_HOST'))
    port = kwargs.get("port", config('DB_PORT'))
    url = f'{host}:{port}'

    if user and password:
        client = MongoClient(
            url,
            username=user,
            password=password,
            authSource=name,
            authMechanism='SCRAM-SHA-1',
            serverSelectionTimeoutMS=1
        )
    else:
        client = MongoClient(url, serverSelectionTimeoutMS=1)

    try:
        client.server_info()  # checking a connection to DB
    except (ServerSelectionTimeoutError, OperationFailure) as err:
        logging.exception("Can't connect to DB: {}".format(err))
        sys.exit(1)

    return client[name]


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
        'user': config('DB_USER_COLLECTION', default='jira_users'),
        'host': config('DB_HOST_COLLECTION', default='jira_hosts'),
        'cache': config('DB_CACHE_COLLECTION', default='cache'),
        'webhook': config('DB_WEBHOOK_COLLECTION', default='webhooks'),
        'subscriptions': config('DB_SUBSCRIPTIONS_COLLECTION', default='subscriptions'),
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

    def _get_collection(self, name):
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

    def is_user_connected(self, telegram_id):
        collection = self._get_collection('user')
        return collection.count({"telegram_id": telegram_id, "auth_method": {"$ne":None}}) > 0

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

    def create_webhook(self, host):
        """
        Creates a webhook
        :param host: jira host
        :return: string webhook ObjectID
        """
        collection = self._get_collection('webhook')
        webhook = collection.insert_one({'host_url': host, 'is_confirmed': False})
        if webhook:
            return str(webhook.inserted_id)

    def update_webhook(self, data, webhook_id=None, host_url=None):
        """
        Updates a webhook data by string ObjectId or host_url
        :param data: dict with updated webhook data
        :type data: dict
        :param webhook_id: string ObjectId
        :param host_url: a host url
        """
        collection = self._get_collection('webhook')
        if webhook_id:
            status = collection.update({'_id': ObjectId(webhook_id)}, {'$set': data})
        elif host_url:
            status = collection.update({'host_url': host_url}, {'$set': data})
        return bool(status)

    def get_webhook(self, webhook_id=None, host_url=None):
        """
        Gets a webhook by webhook_id or host
        :param webhook_id: string ObjectId
        :param host_url: a host url
        :return: a webhook in dict type
        """
        collection = self._get_collection('webhook')
        if webhook_id:
            webhook = collection.find_one({'_id': ObjectId(webhook_id)})
        elif host_url:
            webhook = collection.find_one({'host_url': host_url})
        return webhook

    def create_subscription(self, data):
        """
        Creates a subscription on project or issue
        :param data: dict type
        """
        collection = self._get_collection('subscriptions')
        status = collection.insert_one(data)
        return bool(status)

    def get_subscription(self, chat_id, name):
        """
        Gets a subscription by sub_id
        :param chat_id: a telegram chat id e.g. 283902890
        :param name: an issue key e.g. JTB-99
        :return: a subscription in dict type
        """
        collection = self._get_collection('subscriptions')
        subscription = collection.find_one({'chat_id': chat_id, 'name': name})
        return subscription

    def get_webhook_subscriptions(self, webhook_id):
        """
        Returns all subscriptions linked to a webhook
        :param webhook_id: ObjectId of an exists webhook (webhook collection)
        :return: list of dict subscriptions
        """
        collection = self._get_collection('subscriptions')
        subs = collection.find({'webhook_id': webhook_id})
        return subs

    def get_user_subscriptions(self, user_id):
        """
        Returns all subscriptions linked to a user
        :param user_id: ObjectId of an exists user (user collection)
        :return: list of dict subscriptions
        """
        collection = self._get_collection('subscriptions')
        subs = collection.find({'user_id': user_id})
        return subs

    def delete_subscription(self, chat_id, name):
        """
        Deletes a one subscription was searched by sub_id
        :param chat_id: a telegram chat id e.g. 283902890
        :param name: an issue key e.g. JTB-99
        """
        collection = self._get_collection('subscriptions')
        status = collection.remove({'chat_id': chat_id, 'name': name})
        return bool(status)

    def delete_all_subscription(self, user_id):
        """
        Deletes all subscriptions linked to a user
        :param user_id: ObjectId of an exists user (user collection)
        """
        collection = self._get_collection('subscriptions')
        status = collection.remove({'user_id': user_id})
        return bool(status)

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
