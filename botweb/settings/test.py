from .application import *

# all celery config here is prefixed by `CELERY` due to a `config_from_object` in the main celery config

# host isn't required, but eliminates a warning
CELERY_BROKER_URL = "memory://localhost"

# https://docs.celeryproject.org/en/stable/userguide/configuration.html#std-setting-task_always_eager
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

DATABASES = {"default": dj_database_url.parse(config("TEST_DATABASE_URL"))}

# right now, some tests rely on the ability to pull a valid user config from the ENV
# let's make sure `config` doesn't throw an exception in this case. Since the cassettes
# are recorded when there is a valid ENV-based user configuration we only need to worry
# about this in CI
os.environ.setdefault("USER_LIVEMODE", "true")
if not config("USER_BINANCE_API_KEY", default=None):
    os.environ.setdefault("USER_BINANCE_API_KEY", "")
if not config("USER_BINANCE_SECRET_KEY", default=None):
    os.environ.setdefault("USER_BINANCE_SECRET_KEY", "")
if not config("COINMARKETCAP_API_KEY", default=None):
    os.environ.setdefault("COINMARKETCAP_API_KEY", "")
