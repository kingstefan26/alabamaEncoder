import asyncio
import os
import sys

from aiohttp.web_app import Application
from aiohttp.web_routedef import post
from aiohttp.web_runner import AppRunner, TCPSite

from alabamaEncode.core.job import AlabamaEncodingJob


async def worker(name, queue):
    while True:
        try:
            job = await queue.get()
            await job.run_pipeline()
            queue.task_done()
        except Exception as e:
            print(f"Worker {name} got exception)")
            raise e


async def main():
    worker_count = 1
    queue = asyncio.Queue()
    workers = []
    for i in range(worker_count):
        w = asyncio.create_task(worker(f"worker-{i}", queue))
        workers.append(w)

    # first: queue up old jobs
    # read json jobs from ~/.alabamaEncoder/jobs/*.json, serialize into contexts, build jobs and queue up
    for serialised_job in AlabamaEncodingJob.get_saved_serialised_jobs():
        job = AlabamaEncodingJob.load_from_file(serialised_job)
        if queue.qsize() > 0:
            job.update_current_step_name("Queued")
        print(f"Found and loaded encoding job for {job.ctx.get_title()}")
        queue.put_nowait(job)

    # async version of the server:
    import aiohttp

    auth_bearer = os.environ.get("AUTH_BEARER_TOKEN", "")
    if auth_bearer == "":
        print("No AUTH_BEARER_TOKEN set, exiting")
        sys.exit(1)

    async def handle(request):
        if request.headers.get("Authorization") != f"Bearer {auth_bearer}":
            return aiohttp.web.Response(status=401)

        post_data = await request.read()
        try:
            _job = AlabamaEncodingJob.load_from_file(post_data.decode())
        except Exception as e:
            print(f"Failed to load context from json: {e}")
            return aiohttp.web.Response(status=400)
        if queue.qsize() > 0:
            job.update_current_step_name("Queued")
        print(f"Received encoding job for {_job.ctx.get_title()}")
        queue.put_nowait(_job)
        return aiohttp.web.Response(status=200)

    print("Starting server")
    app = Application()
    app.add_routes([post("/jobs", handle)])
    runner = AppRunner(app)
    await runner.setup()
    site = TCPSite(runner, "", 8000)
    await site.start()


if __name__ == "__main__":
    asyncio.run(main())
