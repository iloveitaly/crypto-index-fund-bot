from dotenv import load_dotenv
load_dotenv()

from celery import Celery

import os

from utils import log
import django.utils.timezone
from commands.buy import BuyCommand

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botweb.settings')

app = Celery('tasks', broker=os.environ['REDIS_URL'])

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
  # this method has a *lot* of kw params that can modify functionality
  sender.add_periodic_task(10.0, initiate_user_buys.s(), name='add every 10')

@app.task
def initiate_user_buys():
  from .models import User

  for user in User.objects.iterator():
    user_buy.delay(user.id)

@app.task
def user_buy(user_id):
  from .models import User

  user = User.objects.get(id=user_id)
  bot_user = user.bot_user()

  log.info("initiating buys for user", user=user)
  BuyCommand.execute(bot_user)

  user.date_checked = django.utils.timezone.now()
  user.save()
