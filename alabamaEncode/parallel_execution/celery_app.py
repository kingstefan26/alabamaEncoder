# get broken/backend url from env
import os
import traceback
from typing import Any

from celery import Celery

from alabamaEncode.parallel_execution.command import BaseCommandObject

BROKER_URL = os.getenv("BROKER_URL", "redis://" + os.getenv("REDIS_HOST", "localhost"))
BACKEND_URL = os.getenv(
    "BACKEND_URL", "redis://" + os.getenv("REDIS_HOST", "localhost")
)

app = Celery("ThaVaidioEncoda", broker=BROKER_URL, backend=BACKEND_URL)

app.conf.update(
    worker_concurrency=8,
    worker_autoscaler="alabamaEncode.CeleryAutoscaler.DAAutoscaler",
    task_serializer="pickle",
    result_serializer="pickle",
    accept_content=["pickle"],
    broker_connection_retry_on_startup=True,
)


@app.task(bind=True)
def run_command_on_celery(self, command: BaseCommandObject) -> Any:
    try:
        return command.run()
    except:
        traceback.print_exc()
