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

        cls.sub_name = 'JTB-99'
        cls.sub_topic = 'issue'

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

    def test_create_webhook(self):
        host = self.db.get_host_data(self.test_host.get('url'))
        webhook_id = self.db.create_webhook(host.get('url'))
        created_webhook = self.db.get_webhook(webhook_id=webhook_id)
        assert created_webhook.get('host_url') == host.get('url')

    def test_update_webhook(self):
        webhook = self.db.get_webhook(host_url=self.test_host.get('url'))
        assert webhook.get('is_confirmed') is False
        self.db.update_webhook({'is_confirmed': True}, host_url=self.test_host.get('url'))
        webhook = self.db.get_webhook(host_url=self.test_host.get('url'))
        assert webhook.get('is_confirmed') is True

    def test_get_webhook(self):
        webhook = self.db.get_webhook(host_url=self.test_host.get('url'))
        assert webhook.get('host_url') == self.test_host.get('url')

    def test_create_subscription(self):
        assert self.db.get_subscription(self.test_user.get('telegram_id'), self.sub_name) is None
        webhook = self.db.get_webhook(host_url=self.test_host.get('url'))
        user = self.db.get_user_data(self.test_user.get('telegram_id'))
        data = {
            'chat_id': user.get('telegram_id'),
            'user_id': user.get('_id'),
            'webhook_id': webhook.get('_id'),
            'topic': self.sub_topic,
            'name': self.sub_name
        }
        self.db.create_subscription(data)

        subscription = self.db.get_subscription(user.get('telegram_id'), self.sub_name)
        assert subscription.get('chat_id') == user.get('telegram_id')
        assert subscription.get('user_id') == user.get('_id')
        assert subscription.get('webhook_id') == webhook.get('_id')
        assert subscription.get('topic') == self.sub_topic
        assert subscription.get('name') == self.sub_name

    def test_get_subscription(self):
        assert self.db.get_subscription('123123', 'JTB-11') is None
        subscription = self.db.get_subscription(self.test_user.get('telegram_id'), self.sub_name)
        webhook = self.db.get_webhook(host_url=self.test_host.get('url'))
        user = self.db.get_user_data(self.test_user.get('telegram_id'))

        assert subscription.get('chat_id') == user.get('telegram_id')
        assert subscription.get('user_id') == user.get('_id')
        assert subscription.get('webhook_id') == webhook.get('_id')
        assert subscription.get('topic') == self.sub_topic
        assert subscription.get('name') == self.sub_name

    def test_get_webhook_subscriptions(self):
        webhook = self.db.get_webhook(host_url=self.test_host.get('url'))
        subs = self.db.get_webhook_subscriptions(webhook.get('_id'))
        assert subs.count() >= 1

    def test_get_user_subscriptions(self):
        user = self.db.get_user_data(self.test_user.get('telegram_id'))
        subs = self.db.get_user_subscriptions(user.get('_id'))
        assert subs.count() >= 1

    def test_delete_subscription(self):
        self.db.delete_subscription(self.test_user.get('telegram_id'), self.sub_name)
        assert self.db.get_subscription(self.test_user.get('telegram_id'), self.sub_name) is None
