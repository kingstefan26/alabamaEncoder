import os
import sys

from alabamaEncode.parallelEncoding.CeleryApp import app


def worker():
    print("Starting celery worker")

    concurrency = 2

    # check if os.environ['CELERY_CONCURRENCY'] is set and set it as the concurrency
    if "CELERY_CONCURRENCY" in os.environ:
        concurrency = os.environ["CELERY_CONCURRENCY"]

    # get the second argument that is the concurrency and set it as the concurrency
    if len(sys.argv) > 2:
        concurrency = sys.argv[2]

    app.worker_main(argv=["worker", "--loglevel=info", f"--concurrency={concurrency}"])
    quit()
