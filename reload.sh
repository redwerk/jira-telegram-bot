#!/bin/bash
set -e

source env/bin/activate

pip install -r requirements.txt
flake8 .

supervisorctl restart bot
supervisorctl restart auth

echo "Server restarted successfully"
