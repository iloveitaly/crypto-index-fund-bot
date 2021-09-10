from .application import *

# all celery config here is prefixed by `CELERY` due to a `config_from_object` in the main celery config

# host isn't required, but eliminates a warning
CELERY_BROKER_URL = "memory://localhost"

# https://docs.celeryproject.org/en/stable/userguide/configuration.html#std-setting-task_always_eager
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

DATABASES = {"default": dj_database_url.parse(config("TEST_DATABASE_URL"))}
SECRET_KEY = config("DJANGO_SECRET_KEY", defaul="django-insecure-@o-)qrym-cn6_*mx8dnmy#m4*$j%8wyy+l=)va&pe)9e7@o4i)")
