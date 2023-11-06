import asyncio
import sys
from asyncio import Future
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from alabamaEncode.adaptive.executor import AdaptiveCommand
from alabamaEncode.parallelEncoding.CeleryApp import run_command_on_celery, app
from alabamaEncode.parallelEncoding.CeleryAutoscaler import Load


async def execute_commands(
    use_celery, command_objects, multiprocess_workers, override_sequential=True
):
    """
    Execute a list of commands in parallel
    :param use_celery: execute on a celery cluster
    :param command_objects: objects with a `run()` method to execute
    :param multiprocess_workers: number of workers in multiprocess mode, -1 for auto adjust
    :param override_sequential: if true, will run sequentially if there are less than 10 scenes
    """
    if len(command_objects) < 10 and override_sequential == True:
        print("Less than 10 scenes, running encodes sequentially")

        for command in command_objects:
            command.run()

    elif use_celery:
        for a in command_objects:
            a.run_on_celery = True

        results = []
        with tqdm(
            total=len(command_objects),
            desc="Encoding",
            unit="scene",
            dynamic_ncols=True,
            smoothing=0,
        ) as pbar:
            for command in command_objects:
                result = run_command_on_celery.delay(command)

                results.append(result)

            while True:
                num_workers = len(app.control.inspect().active_queues())
                if num_workers is None or num_workers < 0:
                    print(
                        "No workers available, waiting for workers to become available"
                    )
                if all(result.ready() for result in results):
                    break
                for result in results:
                    if result.ready():
                        pbar.update()
                        results.remove(result)
    else:
        total_scenes = len(command_objects)
        futures = []
        completed_count = 0

        load = Load()
        target_cpu_utilization = 1.1
        max_swap_usage = 25
        cpu_threshold = 0.3
        concurent_jobs_limit = 2  # Initial value to be adjusted dynamically
        max_limit = sys.maxsize if multiprocess_workers == -1 else multiprocess_workers

        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor()

        # check if the first command is a AdaptiveCommand
        if isinstance(command_objects[0], AdaptiveCommand):
            total_frames = sum([c.chunk.get_frame_count() for c in command_objects])
            pbar = tqdm(
                total=total_frames,
                desc="Encoding",
                unit="frame",
                dynamic_ncols=True,
                unit_scale=True,
            )
        else:
            pbar = tqdm(
                total=total_scenes, desc="Encoding", unit="scene", dynamic_ncols=True
            )

        pbar.set_description(f"Workers: {concurent_jobs_limit} CPU -% SWAP -%")

        while completed_count < total_scenes:
            # Start new tasks if there are available slots
            while (
                len(futures) < concurent_jobs_limit
                and completed_count + len(futures) < total_scenes
            ):
                command = command_objects[completed_count + len(futures)]
                in_executor: Future = loop.run_in_executor(executor, command.run)
                futures.append(in_executor)

            # Wait for any task to complete
            done, _ = await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)

            # Process completed tasks
            for future in done:
                await future
                # if we are encoding chunks update by the done frames, not the done chunks
                if isinstance(command_objects[0], AdaptiveCommand):
                    pbar.update(
                        command_objects[completed_count].chunk.get_frame_count()
                    )
                else:
                    pbar.update()

                completed_count += 1

            # Remove completed tasks from the future list
            futures = [future for future in futures if not future.done()]

            if multiprocess_workers == -1:
                # Check CPU utilization and adjust concurent_jobs_limit if needed
                cpu_utilization = load.get_load()
                swap_usage = load.parse_swap_usage()
                new_limit = concurent_jobs_limit
                if (
                    cpu_utilization < target_cpu_utilization
                    and swap_usage < max_swap_usage
                ):
                    new_limit += 1
                elif (
                    cpu_utilization > target_cpu_utilization + cpu_threshold
                    or swap_usage > max_swap_usage
                ):
                    new_limit -= 1

                # no less than 1 and no more than max_limit
                new_limit = max(1, new_limit)
                if new_limit != concurent_jobs_limit and new_limit <= max_limit:
                    concurent_jobs_limit = new_limit
                    pbar.set_description(
                        f"Workers: {concurent_jobs_limit} CPU {cpu_utilization * 100:.2f}% SWAP {swap_usage:.2f}%"
                    )

        pbar.close()
