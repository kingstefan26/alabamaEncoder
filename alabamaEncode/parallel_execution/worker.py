import os

from alabamaEncode.parallel_execution.celery_app import app


def worker(concurrency=2):
    print("Starting celery worker")

    if "CELERY_CONCURRENCY" in os.environ:
        concurrency = os.environ["CELERY_CONCURRENCY"]

    app.worker_main(argv=["worker", "--loglevel=info", f"--concurrency={concurrency}"])
    quit()
