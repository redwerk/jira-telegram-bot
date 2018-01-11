#!/bin/bash
set -e

source env/bin/activate

pip install -r requirements.txt
flake8 .

supervisorctl restart bot
supervisorctl restart bot_celery
supervisorctl restart botweb

echo "Server restarted successfully"
