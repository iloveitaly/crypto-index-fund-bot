#!/bin/bash -l
set -eu

celery -A users.tasks worker --loglevel=INFO -B --concurrency=1