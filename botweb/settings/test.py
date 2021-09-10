from .application import *

# all celery config here is prefixed by `CELERY` due to a `config_from_object` in the main celery config

# host isn't required, but eliminates a warning
CELERY_BROKER_URL = "memory://localhost"

# https://docs.celeryproject.org/en/stable/userguide/configuration.html#std-setting-task_always_eager
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

DATABASES = {"default": dj_database_url.parse(config("TEST_DATABASE_URL"))}
