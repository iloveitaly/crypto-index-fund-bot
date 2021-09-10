# Usage:
#   docker build -t crypto-index-fund-bot .
#   docker run --env-file .env -it crypto-index-fund-bo#   docker run --env-file .env -it crypto-index-fund-bot bash

# Reference example Dockerfiles:
#   https://medium.com/@harpalsahota/dockerizing-python-poetry-applications-1aa3acb76287
#   https://github.com/monicahq/monica/blob/master/scripts/docker/Dockerfile
#   https://github.com/schickling/dockerfiles/blob/master/mysql-backup-s3/Dockerfile

FROM python:3.9.6

# clean eliminates the need to manually `rm -rf` the cache
RUN set -eux; \
  \
  apt-get update; \
  apt-get install -y --no-install-recommends \
      bash \
#      build-essential libssl-dev libffi-dev libpython3.9-dev cargo \
      cron; \
  apt-get clean;

# TODO this will not work once the cryptography package is updated
#      we must install python3-dev when it's package version is updated to 3.9.6
# https://stackoverflow.com/questions/66118337/how-to-get-rid-of-cryptography-build-error
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

RUN set -eux; \
  pip3 install poetry; \
  poetry config virtualenvs.create false;

# TODO consider using a non-sudo user to run under

ENV DJANGO_SETTINGS_MODULE "botweb.settings.production"

# run every hour by default, use `SCHEDULE=NONE` to run directly
ENV SCHEDULE "0 * * * *"

WORKDIR /app
COPY . ./

# this is the cleanest way to conditionally copy a file
# https://stackoverflow.com/a/46801962/129415
COPY *external_portfolio.json LICENSE ./

# run after copying source to chache the earlier steps
RUN poetry install --no-dev

CMD ["bash", "cron.sh"]
