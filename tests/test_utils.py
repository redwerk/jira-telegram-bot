from common import utils


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
        splitted_issue = utils.split_by_pages(_items, 10)
        assert len(splitted_issue) == pages
        assert len(splitted_issue[-1]) == n_items_at_last_page


def test_validates_hostname():
    hosts = (
        ('https://jira.redwerk.com', True),
        ('https://jira.test.redwerk.com', True),
        ('https://jira.test.redwerk.com/', False),
        ('test', False),
        ('www.test.com', False),
        ('http//test.com', False),
        ('https//test.com', False),
        ('https://test.com', True),
    )

    for host, status in hosts:
        assert status == utils.validates_hostname(host)
