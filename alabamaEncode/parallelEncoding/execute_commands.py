import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import psutil
from tqdm import tqdm

from alabamaEncode.core.chunk_job import ChunkEncoder
from alabamaEncode.parallelEncoding.CeleryApp import run_command_on_celery, app


async def execute_commands(
    use_celery,
    command_objects,
    multiprocess_workers,
    pin_to_cores=False,
    finished_scene_callback=None,
    size_estimate_data=None,
):
    """
    Execute a list of commands in parallel
    :param pin_to_cores:
    :param use_celery: execute on a celery cluster
    :param command_objects: objects with a `run()` method to execute
    :param multiprocess_workers: number of workers in multiprocess mode, -1 for auto adjust
    :param finished_scene_callback: call when a scene finishes, contains the number of finished scenes
    :param size_estimate_data: tuple(frames, kB) of scenes encoded so far for the estimate
    """
    if len(command_objects) == 0:
        return
    are_commands_adaptive_commands = isinstance(command_objects[0], ChunkEncoder)
    # to provide a bitrate estimate in the progress bar
    encoded_frames_so_far = 0
    encoded_size_so_far = 0  # in kbits
    if size_estimate_data is not None:
        encoded_frames_so_far, encoded_size_so_far = size_estimate_data

    if use_celery:
        pbar = tqdm(
            total=sum([c.chunk.get_frame_count() for c in command_objects])
            if are_commands_adaptive_commands
            else len(command_objects),
            desc="Encoding",
            unit="frame" if are_commands_adaptive_commands else "scene",
            dynamic_ncols=True,
            unit_scale=True if are_commands_adaptive_commands else False,
            smoothing=0,
        )

        for a in command_objects:
            a.run_on_celery = True

        running_tasks = [
            run_command_on_celery.delay(command) for command in command_objects
        ]
        pbar.set_description(f"WORKERS - ESTM BITRATE -")

        while True:
            try:
                num_workers = len(app.control.inspect().active_queues())
                if num_workers is None or num_workers < 0:
                    print(
                        "No workers available, waiting for workers to become available"
                    )
                if all(task.ready() for task in running_tasks):
                    break
                for task in running_tasks:
                    if task.ready():
                        result = task.get()
                        if are_commands_adaptive_commands and result is not None:
                            finished_command = command_objects[
                                running_tasks.index(task)
                            ]
                            pbar.update(finished_command.chunk.get_frame_count())
                            pinned_code, stats = result
                            encoded_frames_so_far += stats["length_frames"]
                            encoded_size_so_far += stats["size"]
                            bitrate_estimate = "ESTM BITRATE -"
                            if encoded_frames_so_far > 0:
                                fps = command_objects[0].chunk.framerate
                                bitrate_estimate = (
                                    f"ESTM BITRATE {((encoded_size_so_far * 8) / (encoded_frames_so_far / fps)):.2f} "
                                    f"kb/s"
                                )

                            pbar.set_description(
                                f"WORKERS {num_workers} {bitrate_estimate}"
                            )
                        else:
                            pbar.update()
                        running_tasks.remove(task)
                await asyncio.sleep(1)
            except KeyboardInterrupt as e:
                print("Keyboard interrupt, cancelling tasks")
                for task in running_tasks:
                    task.revoke()
                raise e
        pbar.close()
    else:
        total_scenes = len(command_objects)
        futures, completed_count = [], 0

        core_count, auto_scale = os.cpu_count(), multiprocess_workers == -1
        target_cpu_utilization, max_mem_usage = 95, 80

        max_limit = (
            core_count * 2
            if auto_scale
            else multiprocess_workers
            if multiprocess_workers != -1
            else core_count
        )

        concurrent_jobs_limit = multiprocess_workers if not auto_scale else 2

        loop, executor = asyncio.get_event_loop(), ThreadPoolExecutor()

        used_cores = [0] * core_count

        total_frames = (
            sum([c.chunk.length for c in command_objects])
            if are_commands_adaptive_commands
            else total_scenes
        )
        pbar = tqdm(
            total=total_frames,
            desc="Encoding",
            unit="frame" if are_commands_adaptive_commands else "scene",
            dynamic_ncols=True,
            unit_scale=True,
            smoothing=0,
        )
        if are_commands_adaptive_commands:
            for adapt_cmnd in command_objects:
                adapt_cmnd.encoded_a_frame_callback = (
                    lambda frame, bitrate, fps: pbar.update()
                )

        pbar.set_description(f"WORKERS: - CPU -% SWAP -%")

        while completed_count < total_scenes:
            # Start new tasks if there are available slots
            while (
                len(futures) < concurrent_jobs_limit
                and completed_count + len(futures) < total_scenes
            ):
                command, core = (
                    command_objects[completed_count + len(futures)],
                    used_cores.index(0) if pin_to_cores else None,
                )
                command.pin_to_core = core if pin_to_cores else -1
                future = loop.run_in_executor(executor, command.run)
                futures.append(future)

            done, pending = await asyncio.wait(futures, timeout=7)
            futures = [f for f in futures if not f.done()]

            for future in done:
                rslt = await future
                if are_commands_adaptive_commands and rslt is not None:
                    pined_core: int = rslt[0]
                    stats = rslt[1]
                    if not command_objects[0].supports_encoded_a_frame_callback():
                        pbar.update(
                            command_objects[completed_count].chunk.get_frame_count()
                        )
                    if stats is not None:
                        encoded_frames_so_far += stats["length_frames"]
                        encoded_size_so_far += stats["size"]

                    if pin_to_cores:
                        used_cores[pined_core] = 0
                else:
                    pbar.update()

                completed_count += 1

            cpu_utilization = psutil.cpu_percent()
            mem_usage = psutil.virtual_memory().percent
            bitrate_estimate = "ESTM BITRATE N/A"
            if encoded_frames_so_far > 0:
                fps = command_objects[0].chunk.framerate
                bitrate_estimate = (
                    f"ESTM BITRATE {((encoded_size_so_far * 8) / (encoded_frames_so_far / fps)):.2f} "
                    f"kb/s"
                )
            pbar.set_description(
                f"WORKERS {len(futures)} CPU {int(cpu_utilization)}% "
                f"MEM {int(mem_usage)}% {bitrate_estimate}"
            )

            if auto_scale and len(futures) > 0:
                concurrent_jobs_limit += (
                    1
                    if cpu_utilization <= target_cpu_utilization
                    and mem_usage <= max_mem_usage
                    else -1
                )
                concurrent_jobs_limit = max(1, min(concurrent_jobs_limit, max_limit))

            if finished_scene_callback is not None:
                finished_scene_callback(completed_count)

        pbar.close()
