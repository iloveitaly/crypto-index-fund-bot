from dotenv import load_dotenv
load_dotenv()

from celery import Celery
import os

app = Celery('tasks', broker=os.environ['REDIS_URL'])

@app.task
def add(x, y):
    return x + y