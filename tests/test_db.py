from common import utils
from common.db import MongoBackend
from decouple import config

db = MongoBackend(
    user=config('DB_USER'),
    password=config('DB_PASS'),
    host=config('DB_HOST'),
    port=config('DB_PORT'),
    db_name='test_telegram_jira_db'
)

# user data
test_user = {
    'telegram_id': 208810143,
    'host_url': None,
    'username': None,
    'auth_method': None,
    'auth': {
        'oauth': dict(access_token=None, access_token_secret=None),
        'basic': dict(password=None),
    },
}
updated_user_data = {
        'username': 'test_user',
        'auth.basic.password': 'test_pass'
    }

# host data
test_host = {
    'url': 'https://jira.redwerk.com',
    'is_confirmed': False,
    'consumer_key': utils.generate_consumer_key(),
}
update_test_host = {
    'consumer_key': utils.generate_consumer_key(),
    'is_confirmed': True
}

# cache data
item_per_page = 10
test_cache_item = utils.split_by_pages(['test_cache{}'.format(i) for i in range(25)], item_per_page)
test_cache_key = 'test_cache:{}'.format(test_user.get('telegram_id'))


def test_create_user():
    status = db.create_user(test_user)
    created_user = db.get_user_data(test_user.get('telegram_id'))
    assert status is True
    assert test_user.get('telegram_id') == created_user.get('telegram_id')


def test_update_user():
    status = db.update_user(test_user.get('telegram_id'), updated_user_data)
    updated_user = db.get_user_data(test_user.get('telegram_id'))
    assert status is True
    assert updated_user.get('username') == updated_user_data.get('username')
    assert updated_user['auth']['basic']['password'] == updated_user_data.get('auth.basic.password')


def test_is_user_exists():
    existent_user = db.is_user_exists(test_user.get('telegram_id'))
    fake_user = db.is_user_exists(1256321)
    assert existent_user is True
    assert fake_user is False


def test_get_user_data():
    existent_user = db.get_user_data(test_user.get('telegram_id'))
    assert existent_user.get('telegram_id') == test_user.get('telegram_id')
    assert existent_user.get('username') == updated_user_data.get('username')
    assert existent_user.get('host_url') is None
    assert existent_user.get('auth_method') is None
    assert existent_user['auth']['basic']['password'] == updated_user_data.get('auth.basic.password')
    assert existent_user['auth']['oauth']['access_token'] is None
    assert existent_user['auth']['oauth']['access_token'] is None


def test_create_host():
    status = db.create_host(test_host)
    created_host = db.get_host_data(test_host.get('url'))
    assert status is True
    assert created_host.get('url') == test_host.get('url')


def test_update_host():
    status = db.update_host(test_host.get('url'), update_test_host)
    updated_host = db.get_host_data(test_host.get('url'))
    assert status is True
    assert updated_host.get('url') == test_host.get('url')
    assert updated_host.get('is_confirmed') is True
    assert updated_host.get('consumer_key') == update_test_host.get('consumer_key')


def test_get_host_data():
    host = db.get_host_data(test_host.get('url'))
    assert host.get('url') == test_host.get('url')
    assert host.get('is_confirmed') is True
    assert host.get('consumer_key') == update_test_host.get('consumer_key')


def test_search_host():
    existent_host = db.search_host('jira.redwerk.com')
    fake_host = db.search_host('jira.greenwerk.com')
    assert fake_host is None
    assert existent_host.get('url') == test_host.get('url')
    assert existent_host.get('is_confirmed') is True
    assert existent_host.get('consumer_key') == update_test_host.get('consumer_key')


def test_create_cache():
    status = db.create_cache(test_cache_key, test_cache_item, item_per_page)
    assert status is True


def test_get_cached_content():
    created_cashe = db.get_cached_content(test_cache_key)
    fake_cache = db.get_cached_content('test_cache')
    assert fake_cache == dict()
    assert len(created_cashe.get('content')) == len(test_cache_item)
    assert created_cashe.get('page_count') == item_per_page


def test_clean_db():
    db._get_collection('user').drop()
    db._get_collection('host').drop()
    db._get_collection('cache').drop()
    assert db.is_user_exists(test_user.get('telegram_id')) is False
    assert db.get_host_data(test_host.get('url')) is None
    assert db.get_cached_content(test_cache_key) == dict()
