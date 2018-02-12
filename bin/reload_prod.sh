#!/bin/bash
set -e

source venv/bin/activate

pip install -r requirements.txt
flake8 .

supervisorctl restart jirabot
supervisorctl restart jirabot_celery
supervisorctl restart jirabot_web

echo "Server restarted successfully"
