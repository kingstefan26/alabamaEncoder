import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from alabamaEncode.adaptive.executor import AdaptiveCommand
from alabamaEncode.parallelEncoding.CeleryApp import run_command_on_celery, app
from alabamaEncode.parallelEncoding.CeleryAutoscaler import Load


async def execute_commands(
    use_celery,
    command_objects,
    multiprocess_workers,
    override_sequential=True,
    pin_to_cores=False,
):
    """
    Execute a list of commands in parallel
    :param pin_to_cores:
    :param use_celery: execute on a celery cluster
    :param command_objects: objects with a `run()` method to execute
    :param multiprocess_workers: number of workers in multiprocess mode, -1 for auto adjust
    :param override_sequential: if true, will run sequentially if there are less than 10 scenes
    """
    # if len(command_objects) < 10 and override_sequential == True:
    #     print("Less than 10 scenes, running encodes sequentially")
    #
    #     for command in command_objects:
    #         command.run()
    #
    # elif use_celery:
    if use_celery:
        is_adaptive_command = isinstance(command_objects[0], AdaptiveCommand)
        if is_adaptive_command:
            total_frames = sum([c.chunk.get_frame_count() for c in command_objects])
            pbar = tqdm(
                total=total_frames,
                desc="Encoding",
                unit="frame",
                dynamic_ncols=True,
                unit_scale=True,
                smoothing=0,
            )
        else:
            pbar = tqdm(
                total=len(command_objects),
                desc="Encoding",
                unit="scene",
                dynamic_ncols=True,
                smoothing=0,
            )

        for a in command_objects:
            a.run_on_celery = True

        running_tasks = [
            run_command_on_celery.delay(command) for command in command_objects
        ]

        while True:
            num_workers = len(app.control.inspect().active_queues())
            if num_workers is None or num_workers < 0:
                print("No workers available, waiting for workers to become available")
            if all(result.ready() for result in running_tasks):
                break
            for task in running_tasks:
                if task.ready():
                    if is_adaptive_command:
                        pbar.update(
                            command_objects[
                                running_tasks.index(task)
                            ].chunk.get_frame_count()
                        )
                    else:
                        pbar.update()
                    running_tasks.remove(task)
                    await asyncio.sleep(1)
        pbar.close()
    else:
        total_scenes = len(command_objects)
        futures = []
        completed_count = 0

        load = Load()
        core_count = os.cpu_count()
        auto_scale = multiprocess_workers == -1

        target_cpu_utilization = 1.1
        max_swap_usage = 25
        cpu_threshold = 0.3

        if pin_to_cores == -1:
            if auto_scale:
                max_limit = core_count * 2
            else:
                max_limit = multiprocess_workers
        else:
            max_limit = core_count

        concurrent_jobs_limit = 2  # Initial value to be adjusted dynamically
        if not auto_scale:
            concurrent_jobs_limit = multiprocess_workers

        loop = asyncio.get_event_loop()

        executor = ThreadPoolExecutor()

        used_cores = [0] * core_count

        # check if the first command is a AdaptiveCommand
        if isinstance(command_objects[0], AdaptiveCommand):
            total_frames = sum([c.chunk.get_frame_count() for c in command_objects])
            pbar = tqdm(
                total=total_frames,
                desc="Encoding",
                unit="frame",
                dynamic_ncols=True,
                unit_scale=True,
                smoothing=0,
            )
            for adapt_cmnd in command_objects:
                adapt_cmnd.encoded_a_frame_callback = (
                    lambda frame, bitrate, fps: pbar.update()
                )
        else:
            pbar = tqdm(
                total=total_scenes, desc="Encoding", unit="scene", dynamic_ncols=True
            )

        pbar.set_description(f"Workers: 0 CPU -% SWAP -%")

        while completed_count < total_scenes:
            cpu_utilization = load.get_load()

            # Start new tasks if there are available slots
            while (
                len(futures) < concurrent_jobs_limit
                and completed_count + len(futures) < total_scenes
            ):
                command = command_objects[completed_count + len(futures)]
                if pin_to_cores:
                    # find the first available core
                    core = used_cores.index(0)
                    # mark the core as used
                    used_cores[core] = 1
                    command.pin_to_core = core
                futures.append(loop.run_in_executor(executor, command.run))

            # Wait for any task to complete
            # done, _ = await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)

            # alt version where we wait one sec and loop
            done, _ = await asyncio.wait(futures, timeout=5)

            # Process completed tasks
            for future in done:
                result = await future  # result is the command object run() output
                # if we are encoding chunks update by the done frames, not the done chunks
                if isinstance(command_objects[0], AdaptiveCommand):
                    if not command_objects[0].supports_encoded_a_frame_callback():
                        # if the encoder does not support encoded a frame callback,
                        # update by the number of frames in the chunk,
                        # otherwise the callback above will update the progress bar
                        pbar.update(
                            command_objects[completed_count].chunk.get_frame_count()
                        )
                else:
                    pbar.update()

                if pin_to_cores:
                    # in this case the result is the AdaptiveCommand object, which returns the core it was pinned to
                    # mark the core as unused
                    used_cores[result] = 0

                completed_count += 1

            # Remove completed tasks from the future list
            futures = [future for future in futures if not future.done()]

            pbar.set_description(
                f"Workers: {len(futures)} CPU {cpu_utilization * 100:.2f}% "
                # f"SWAP {swap_usage:.2f}%"
            )

            if auto_scale and len(futures) > 0:
                # swap_usage = parse_swap_usage()
                if (
                    cpu_utilization
                    < target_cpu_utilization
                    # and swap_usage < max_swap_usage
                ):
                    concurrent_jobs_limit += 1
                elif (
                    cpu_utilization
                    > target_cpu_utilization + cpu_threshold
                    # or swap_usage > max_swap_usage
                ):
                    concurrent_jobs_limit -= 1

                # no less than 1 and no more than max_limit
                concurrent_jobs_limit = max(1, min(concurrent_jobs_limit, max_limit))

        pbar.close()
