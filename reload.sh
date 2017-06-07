#!/bin/bash
set -e

source env/bin/activate

pip install -r requirements.txt
flake8 .
pid_file="./tmp/bot.pid"

if [ -f "$pid_file" ]
then
    echo "KILL bot procces"
    cat $pid_file | xargs kill
    echo "Waiting....";
    for i in {5..1}
    do
        echo $i
        sleep 1
    done
fi

echo "bot reloading"
