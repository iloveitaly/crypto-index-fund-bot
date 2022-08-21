# Usage:
#   docker build -t crypto-index-fund-bot .
#   docker run --env-file .env -it crypto-index-fund-bo#   docker run --env-file .env -it crypto-index-fund-bot bash

# Reference example Dockerfiles:
#   https://medium.com/@harpalsahota/dockerizing-python-poetry-applications-1aa3acb76287
#   https://github.com/monicahq/monica/blob/master/scripts/docker/Dockerfile
#   https://github.com/schickling/dockerfiles/blob/master/mysql-backup-s3/Dockerfile

FROM python:3.9.13

LABEL maintainer="Michael Bianco <mike@mikebian.co>"
LABEL org.opencontainers.image.source=https://github.com/iloveitaly/crypto-index-fund-bot

# clean eliminates the need to manually `rm -rf` the cache
RUN set -eux; \
  \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    bash \
    nano \
    locales \
    # TODO figure out how to build a recent version of rust that's supported on the pi
    #      build-essential libssl-dev libffi-dev libpython3.9-dev cargo \
    cron; \
  # this is required for the `locale` settings for the CLI to work
  # https://stackoverflow.com/questions/14547631/python-locale-error-unsupported-locale-setting
  # https://stackoverflow.com/questions/59633558/python-based-dockerfile-throws-locale-error-unsupported-locale-setting
  sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen; \
  locale-gen; \
  apt-get clean;

RUN set -eux; \
  pip3 install poetry==1.1.14; \
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

CMD ["bash", "scripts/cron.sh"]
