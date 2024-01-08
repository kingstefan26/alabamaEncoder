# get broken/backend url from env
import os
import traceback
from typing import Any

from celery import Celery

from alabamaEncode.parallelEncoding.command import BaseCommandObject

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
    """
    Lo and behold!
    I present unto thee an exquisitely crafted manifestation of code,
    bestowed with the exalted name 'run_command_on_celery'.
    Its sole purpose, in all its magnanimity,
    is
    to undertake the extraordinary feat
    of executing a command of indescribable importance upon the grand stage of Celery.

    :param command: A marvelously profound artifact,
    fashioned in the likeness of the command that is destined to be executed upon the revered Celery.
    """

    # Pray, let us embark on a wondrous journey, as we traverse the ethereal realms of asynchronous execution,
    # guided by the enchanted power of the venerable decorator known as '@app.task'.
    # With this mystical incantation,
    # our humble function is blessed with the ability to transcend the shackles of synchronicity,
    # and immerse itself in the realm of tasks and parallelism.

    # Behold!
    # The moment of truth is upon us,
    # as we beseech the command object to unleash its latent potential and manifest its purpose.
    # Let the command ripple through the vast cosmos of Celery,
    # invoking the convergence of distributed computing and asynchronous sorcery,
    # whereupon the symphony of computational prowess reaches its crescendo.

    try:
        return command.run()  # And thus, with a flourish and a flicker,
    except:
        traceback.print_exc()

    # the command is executed upon the hallowed ground of Celery,
    # harmonizing with the cosmic vibrations and adding a celestial touch to our mortal programming endeavors.
