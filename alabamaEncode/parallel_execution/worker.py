import os
import sys

from alabamaEncode.parallel_execution.celery_app import app


def worker():
    print("Starting celery worker")

    concurrency = 2

    if "CELERY_CONCURRENCY" in os.environ:
        concurrency = os.environ["CELERY_CONCURRENCY"]

    if len(sys.argv) > 2:
        concurrency = sys.argv[2]

    app.worker_main(argv=["worker", "--loglevel=info", f"--concurrency={concurrency}"])
    quit()
