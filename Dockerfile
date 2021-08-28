# Usage:
#   docker build -t crypto-index-fund-bot .
#   docker run --env-file .env -it crypto-index-fund-bot
#   docker run --env-file .env -it crypto-index-fund-bot bash

# Reference example Dockerfiles:
#   https://medium.com/@harpalsahota/dockerizing-python-poetry-applications-1aa3acb76287
#   https://github.com/monicahq/monica/blob/master/scripts/docker/Dockerfile
#   https://github.com/schickling/dockerfiles/blob/master/mysql-backup-s3/Dockerfile

FROM python:3.9

# clean eliminates the need to manually `rm -rf` the cache
RUN set -eux; \
  \
  apt-get update; \
  apt-get install -y --no-install-recommends \
      bash \
      cron; \
  apt-get clean;

RUN set -eux; \
  pip3 install poetry; \
  poetry config virtualenvs.create false;

# run every hour by default, use `SCHEDULE=NONE` to run directly
ENV SCHEDULE "0 * * * *"

WORKDIR /app
COPY . ./

# this is the cleanest way to conditionally copy a file
# https://stackoverflow.com/a/46801962/129415
COPY *external_portfolio.json ./

# run after copying source to chache the earlier steps
RUN poetry install --no-dev

CMD ["bash", "cron.sh"]