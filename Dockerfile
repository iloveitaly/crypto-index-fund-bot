# Usage:
#   docker build -t crypto-index-fund-bot .
#   docker run --env-file .env -it crypto-index-fund-bo#   docker run --env-file .env -it crypto-index-fund-bot bash

# Reference example Dockerfiles:
#   https://medium.com/@harpalsahota/dockerizing-python-poetry-applications-1aa3acb76287
#   https://github.com/monicahq/monica/blob/master/scripts/docker/Dockerfile
#   https://github.com/schickling/dockerfiles/blob/master/mysql-backup-s3/Dockerfile

FROM python:3.9.6

LABEL maintainer="Michael Bianco <mike@mikebian.co>"

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

# TODO this will not work once the cryptography package is updated
#      we must install python3-dev when it's package version is updated to 3.9.6
# https://stackoverflow.com/questions/66118337/how-to-get-rid-of-cryptography-build-error
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

RUN set -eux; \
  # lock to specific version to avoid rust compilation
  pip3 install cryptography==3.4.8; \
  pip3 install poetry==1.1.11; \
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
