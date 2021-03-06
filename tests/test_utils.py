import pendulum
import pytest

from web.webhooks.views import IssueWebhookView
from bot.exceptions import DateTimeValidationError
from bot.paginations import split_by_pages
from lib import utils


def test_password_encryption_decryption():
    password = '9Un6!jiu6Va%3R!w'
    encrypted_password = utils.encrypt_password(password)
    decrypted_password = utils.decrypt_password(encrypted_password)
    assert password == decrypted_password


def test_split_by_pages():
    items = (
        (4, 3, [i for i in range(33)]),  # 33 items on 4 pages, 3 items at last page
        (1, 8, [i for i in range(8)]),  # 8 items on 1 page, 8 items at last page
        (20, 10, [i for i in range(200)])  # 200 items on 20 pages, 10 items at last page
    )
    for pages, n_items_at_last_page, _items in items:
        splitted_issue = split_by_pages(_items, 10)
        assert len(splitted_issue) == pages
        assert len(splitted_issue[-1]) == n_items_at_last_page


def test_validates_hostname():
    hosts = (
        ('https://google.com', True),
        ('https://google.com/', False),
        ('test', False),
        ('www.test.com', False),
        ('http//test.com', False),
        ('https//test.com', False),
        ('https://test.com', True),
    )

    for host, status in hosts:
        assert status == utils.validates_hostname(host)


def test_validate_date_range():
    start_date = pendulum.parse('22.11.2017')
    end_date = pendulum.parse('25.11.2017')

    answer = utils.validate_date_range(start_date, end_date)
    assert answer is None

    start_date = pendulum.now()
    with pytest.raises(DateTimeValidationError, message='End date cannot be less than the start date'):
        utils.validate_date_range(start_date, end_date)


def test_calculate_tracking_time():
    seconds = 17800
    assert 4.94 == utils.calculate_tracking_time(seconds)
    assert 0.0 == utils.calculate_tracking_time(0)


def test_filters_subscribers():
    subs = [
        {'topic': 'project', 'name': 'JA', 'chat_id': 208810129},
        {'topic': 'project', 'name': 'JTB', 'chat_id': 2010129},
        {'topic': 'project', 'name': 'IHB', 'chat_id': 2088129},
        {'topic': 'project', 'name': 'CORP', 'chat_id': 8810129},
        {'topic': 'issue', 'name': 'JTB-99', 'chat_id': 208810789},
        {'topic': 'issue', 'name': 'IHB-1', 'chat_id': 208810987},
        {'topic': 'issue', 'name': 'CORP-11', 'chat_id': 20881},
        {'topic': 'issue', 'name': 'JA-241', 'chat_id': 10789},
    ]
    assert {208810129} == IssueWebhookView.filters_subscribers(subs, project='JA')
    assert {2010129, 208810789} == IssueWebhookView.filters_subscribers(subs, project='JTB', issue='JTB-99')
