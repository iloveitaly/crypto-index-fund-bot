import os

import django.utils.timezone
from celery import Celery

from bot.commands import BuyCommand

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "botweb.settings.development")

app = Celery("tasks")

app.config_from_object("django.conf:settings", namespace="CELERY")

from django_structlog.celery.steps import DjangoStructLogInitStep

assert app.steps is not None
app.steps["worker"].add(DjangoStructLogInitStep)

from celery.signals import setup_logging


@setup_logging.connect
def receiver_setup_logging(loglevel, logfile, format, colorize, **kwargs):  # pragma: no cover
    # not sure exactly why, but just defining this function fixed colorization formatting in celery
    # it seems to eliminate the default logging wrapper which mutates the log formatting
    pass


assert app.on_after_configure is not None


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # this method has a *lot* of kw params that can modify functionality
    sender.add_periodic_task(60 * 60, initiate_user_buys.s(), name="check all accounts every hour for updates")


@app.task
def initiate_user_buys():
    from .models import User

    for user in User.objects.iterator():
        user_buy.delay(user.id)


@app.task
def user_buy(user_id):
    import bot.utils

    from .models import User

    user = User.objects.get(id=user_id)
    bot_user = user.bot_user()

    import sentry_sdk

    sentry_sdk.set_user({"id": user_id, "username": user.name})

    bot.utils.log.bind(user_id=user.id)
    bot.utils.log.info("initiating buys for user")

    BuyCommand.execute(bot_user)

    user.date_checked = django.utils.timezone.now()
    user.save()
