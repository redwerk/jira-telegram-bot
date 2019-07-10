from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton

from .inlinemenu import build_menu


def split_by_pages(issues, item_per_page):
    """
    Return list of lists. Each list contains elements associated to
    page number + 1.

    exp: issues = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    items_by_pages = split_by_pages(issues, 3) # 3 items per page
    items_by_pages # [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]

    page = 4 # want to get items from page 4
    items_by_pages[page + 1] # [10]

    :param issues: list of items
    :param item_per_page: count of items per page
    :return: list of lists
    """
    splitted_issues = list()
    for start in range(0, len(issues), item_per_page):
        splitted_issues.append(issues[start:start + item_per_page])

    return splitted_issues


def get_pagination_keyboard(current, max_page, str_key):
    """
    Generating an inline keyboard for displaying pagination
    :param current: selected page number
    :param max_page: max page number for displaying in keyboard
    :param str_key: some key for different handlers
    :return: list from formed inline buttons
    """
    inline_buttons = []
    if current > 1:
        inline_buttons.append(
            InlineKeyboardButton(
                '« 1',
                callback_data=str_key.format('1')
            )
        )

    if current > 2:
        inline_buttons.append(
            InlineKeyboardButton(
                '< {}'.format(current - 1),
                callback_data=str_key.format(current - 1)
            )
        )

    if current < max_page - 1:
        inline_buttons.append(
            InlineKeyboardButton(
                '{} >'.format(current + 1),
                callback_data=str_key.format(current + 1)
            )
        )

    if current < max_page:
        inline_buttons.append(
            InlineKeyboardButton(
                '{} »'.format(max_page),
                callback_data=str_key.format(max_page)
            )
        )

    return InlineKeyboardMarkup(build_menu(inline_buttons, n_cols=len(inline_buttons)))
