from .application import *

from decouple import config

if sentry_dsn := config("SENTRY_DSN", default=None):
    assert isinstance(sentry_dsn, str)

    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
    )
