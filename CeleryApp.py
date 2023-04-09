# get broken/backend url from env
import os

from celery import Celery

BROKER_URL = os.getenv('BROKER_URL', 'redis://' + os.getenv('REDIS_HOST', 'localhost'))
BACKEND_URL = os.getenv('BACKEND_URL', 'redis://' + os.getenv('REDIS_HOST', 'localhost'))

app = Celery('ThaVaidioEncoda', broker=BROKER_URL, backend=BACKEND_URL)

app.conf.update(
    worker_concurrency=8,
    worker_autoscaler='paraliezeMeHoe.CeleryAutoscaler.DAAutoscaler',
    task_serializer='pickle',
    result_serializer='pickle',
    accept_content=['pickle']
)
