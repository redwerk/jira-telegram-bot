import time

from bot.paginations import split_by_pages
from lib import utils

from .base import JTBTest


class TestMongoBackend(JTBTest):

    def setup_class(cls):
        super().setup_class(cls)
        # user data
        cls.test_user = {
            'telegram_id': 208810143,
            'host_url': None,
            'username': None,
            'auth_method': None,
            'auth': {
                'oauth': dict(access_token=None, access_token_secret=None),
                'basic': dict(password=None),
            },
        }
        cls.updated_user_data = {
            'username': 'test_user',
            'auth.basic.password': 'test_pass'
        }

        # host data
        cls.test_host = {
            'url': 'https://jira.redwerk.com',
            'is_confirmed': False,
            'consumer_key': utils.generate_consumer_key(),
        }
        cls.update_test_host = {
            'consumer_key': utils.generate_consumer_key(),
            'is_confirmed': True
        }

        # cache data
        cls.item_per_page = 10
        cls.test_cache_item = split_by_pages(['test_cache{}'.format(i) for i in range(25)], cls.item_per_page)
        cls.test_cache_key = 'test_cache:{}'.format(cls.test_user.get('telegram_id'))
        cls.test_cache_title = 'Test cached items'

    def test_create_user(self):
        status = self.db.create_user(self.test_user)
        created_user = self.db.get_user_data(self.test_user.get('telegram_id'))
        assert status is True
        assert self.test_user.get('telegram_id') == created_user.get('telegram_id')

    def test_update_user(self):
        status = self.db.update_user(self.test_user.get('telegram_id'), self.updated_user_data)
        updated_user = self.db.get_user_data(self.test_user.get('telegram_id'))
        assert status is True
        assert updated_user.get('username') == self.updated_user_data.get('username')
        assert updated_user['auth']['basic']['password'] == self.updated_user_data.get('auth.basic.password')

    def test_is_user_exists(self):
        existent_user = self.db.is_user_exists(self.test_user.get('telegram_id'))
        fake_user = self.db.is_user_exists(1256321)
        assert existent_user is True
        assert fake_user is False

    def test_get_user_data(self):
        existent_user = self.db.get_user_data(self.test_user.get('telegram_id'))
        assert existent_user.get('telegram_id') == self.test_user.get('telegram_id')
        assert existent_user.get('username') == self.updated_user_data.get('username')
        assert existent_user.get('host_url') is None
        assert existent_user.get('auth_method') is None
        assert existent_user['auth']['basic']['password'] == self.updated_user_data.get('auth.basic.password')
        assert existent_user['auth']['oauth']['access_token'] is None
        assert existent_user['auth']['oauth']['access_token'] is None

    def test_create_host(self):
        status = self.db.create_host(self.test_host)
        created_host = self.db.get_host_data(self.test_host.get('url'))
        assert status is True
        assert created_host.get('url') == self.test_host.get('url')

    def test_update_host(self):
        status = self.db.update_host(self.test_host.get('url'), self.update_test_host)
        updated_host = self.db.get_host_data(self.test_host.get('url'))
        assert status is True
        assert updated_host.get('url') == self.test_host.get('url')
        assert updated_host.get('is_confirmed') is True
        assert updated_host.get('consumer_key') == self.update_test_host.get('consumer_key')

    def test_get_host_data(self):
        host = self.db.get_host_data(self.test_host.get('url'))
        assert host.get('url') == self.test_host.get('url')
        assert host.get('is_confirmed') is True
        assert host.get('consumer_key') == self.update_test_host.get('consumer_key')

    def test_search_host(self):
        existent_host = self.db.search_host('jira.redwerk.com')
        fake_host = self.db.search_host('jira.greenwerk.com')
        assert fake_host is None
        assert existent_host.get('url') == self.test_host.get('url')
        assert existent_host.get('is_confirmed') is True
        assert existent_host.get('consumer_key') == self.update_test_host.get('consumer_key')

    def test_create_cache(self):
        status = self.db.create_cache(
            self.test_cache_key,
            self.test_cache_title,
            self.test_cache_item,
            self.item_per_page
        )
        assert status is True

    def test_get_cached_content(self):
        created_cashe = self.db.get_cached_content(self.test_cache_key)
        fake_cache = self.db.get_cached_content('test_cache')
        assert fake_cache == dict()
        assert len(created_cashe.get('content')) == len(self.test_cache_item)
        assert created_cashe.get('page_count') == self.item_per_page
        assert created_cashe.get('title') == self.test_cache_title

    def test_get_cached_content_after_expired(self):
        time.sleep(60)  # need time to build an index
        created_cashe = self.db.get_cached_content(self.test_cache_key)
        assert created_cashe == dict()
