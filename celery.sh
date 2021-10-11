#!/bin/bash -l
set -eu

celery -A users worker --loglevel=INFO -B --concurrency=1