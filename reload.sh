#!/bin/bash
set -e

source env/bin/activate

pip install -r requirements.txt
flake8 .

sudo supervisorctl restart bot
sudo supervisorctl restart auth

echo "Server restarted successfully"
