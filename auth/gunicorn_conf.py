import os

TMP = os.path.expanduser("~/jira-telegram-bot/tmp/")


def numCPUs():
    if not hasattr(os, "sysconf"):
        raise RuntimeError("No sysconf detected.")
    return os.sysconf("SC_NPROCESSORS_ONLN")


port = os.environ.get('GUNICORN_PORT', 9000)
bind = "127.0.0.1:%s" % port
workers = numCPUs() + 1
worker_class = "gevent"
max_requests = 1000
daemon = False
pidfile = TMP + "auth_g.pid"
accesslog = TMP + "auth_g.access.log"
errorlog = TMP + "auth_g.error.log"
graceful_timeout = 60
timeout = 300
keepalive = 0
