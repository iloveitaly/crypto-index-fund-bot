import os

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "botweb.settings.development")

# the load order of celery matters here; if this is not loaded before django components celery will fail to start
from celery import Celery  # isort:skip

app = Celery("tasks")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

from django_structlog.celery.steps import DjangoStructLogInitStep

assert app.steps is not None
app.steps["worker"].add(DjangoStructLogInitStep)

import django.utils.timezone
import sentry_sdk
from celery.signals import setup_logging

from bot.commands import BuyCommand
from bot.utils import log


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
    from users.models import User

    log.info("initiating all buys for user")

    # TODO using `iterator` here was causing the queryset contents to be cached
    for user in User.objects.all():
        user_buy.delay(user.id)


@app.task
def user_buy(user_id):
    from users.models import User

    user = User.objects.get(id=user_id)

    if user.disabled:
        log.info("user is disabled, skipping", user=user)
        return

    bot_user = user.bot_user()

    sentry_sdk.set_user({"id": user_id, "username": user.name})

    log.bind(user_id=user.id)
    log.info("initiating buys for user")

    buy_results_by_exchange = BuyCommand.execute(bot_user)

    # TODO this data structure is pretty messy
    # aggregate buy results
    completed_orders = []
    for (_, _, _, completed_orders_in_exchange) in buy_results_by_exchange:
        completed_orders += completed_orders_in_exchange

    if len(completed_orders) > 0:
        log.info("completed orders", completed_orders=len(completed_orders))
        user.last_ordered_at = django.utils.timezone.now()

    user.date_checked = django.utils.timezone.now()
    user.save()
