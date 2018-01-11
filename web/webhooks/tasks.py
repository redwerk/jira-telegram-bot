import requests

from ..app import celery, logger


@celery.task(bind=True, rate_limit='30/s')
def send_message(self, url):
    """Send message into a user chat.

    If response status is 429 - returns message into queue and tries
    message sending again later. You should run this task in queue with
    30 concurrency workers.

    Arguments:
        url (str): prepared url to telegram API
    """
    try:
        status = requests.get(url)
    except requests.RequestException as error:
        logger.error(f'{url}\n{error}')
    else:
        if status.status_code == 429:
            raise self.retry()
