from decouple import config
from pymongo import MongoClient

from lib.db import MongoBackend


class JTBTest:

    def setup_class(cls):
        # creates a test database and initialize all test data
        cls.test_db_name = 'test_' + config('DB_NAME')
        cls.client = MongoClient('{host}:{port}'.format(host=config('DB_HOST'), port=config('DB_PORT')))
        cls.client.admin.authenticate(config('DB_USER'), config('DB_PASS'))
        cls.client[cls.test_db_name].add_user(
            config('DB_USER'),
            config('DB_PASS'),
            roles=[{'role': 'readWrite', 'db': cls.test_db_name}]
        )
        cls.db = MongoBackend(db_name=cls.test_db_name)

        # creates a collection and index (TTL with expire after 5 seconds)
        test_client = cls.db.conn
        cache_name = config('DB_CACHE_COLLECTION')
        test_client.create_collection(cache_name)
        test_client[cache_name].create_index('createdAt', expireAfterSeconds=5, background=True)

    def teardown_class(cls):
        # drops a database after calling all test cases
        cls.client.drop_database(cls.test_db_name)
