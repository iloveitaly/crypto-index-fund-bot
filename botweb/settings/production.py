from .application import *

from decouple import config

if sentry_dsn := config("SENTRY_DSN", default=False)
  import sentry_sdk
  sentry_sdk.init(
    sentry_dsn,
    traces_sample_rate=1.0,
  )