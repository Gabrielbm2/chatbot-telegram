#!/bin/bash

LOCK_FILE="/tmp/my_telegram_bot.lock"

cleanup() {
    echo "Cleaning up..."
    rm -f $LOCK_FILE
    exit
}

trap cleanup INT TERM EXIT

if [ -f $LOCK_FILE ]; then
    echo "Another instance is already running. Exiting..."
    exit 1
else
    touch $LOCK_FILE
    echo "Starting bot..."
    python app.py > /var/log/my_telegram_bot.log 2>&1
    status=$?
    rm -f $LOCK_FILE
    exit $status
fi