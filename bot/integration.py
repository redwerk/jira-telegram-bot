import jira
from decouple import config
import logging


def jira_connection(func):
    def wrapper(*args, **kwargs):
        username = kwargs.get('username')
        password = kwargs.get('password')
        data = None

        try:
            jira_conn = jira.JIRA(
                server=config('JIRA_HOST'),
                basic_auth=(username, password),
                max_retries=1
            )
        except jira.JIRAError as e:
            logging.info('{}'.format(e.status_code))
        else:
            data = func(*args, **kwargs)
            jira_conn.kill_session()

        return data

    return wrapper


class JiraBackend(object):
    @jira_connection
    def get_open_tickets(self, *args, **kwargs):
        username = kwargs.get('username')
        return username

if __name__ == '__main__':
    jira_obj = JiraBackend()
    a = jira_obj.get_open_tickets(username='iperesunko', password='test')
    print(a)
