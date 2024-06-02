import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

import psutil
from tqdm import tqdm

from alabamaEncode.core.chunk_job import ChunkEncoder
from alabamaEncode.parallel_execution.celery_app import run_command_on_celery, app
from alabamaEncode.parallel_execution.command import BaseCommandObject


async def execute_commands(
    use_celery=False,
    command_objects: List[BaseCommandObject] = None,
    multiprocess_workers: int = -1,
    pin_to_cores=False,
    finished_scene_callback: callable = None,
    size_estimate_data: tuple = None,
    throughput_scaling=False,
    pbar: tqdm = None,
):
    """
    Execute a list of commands in parallel
    :param throughput_scaling:
    :param pbar:
    :param pin_to_cores:
    :param use_celery: execute on a celery cluster
    :param command_objects: objects with a `run()` method to execute
    :param multiprocess_workers: number of workers in multiprocess mode, -1 for auto adjust
    :param finished_scene_callback: call when a scene finishes, contains the number of finished scenes
    :param size_estimate_data: tuple(frames, kB) of scenes encoded so far for the estimate
    """
    if command_objects is None or len(command_objects) == 0:
        return
    are_commands_adaptive_commands = isinstance(command_objects[0], ChunkEncoder)

    # this is for pure ide convince; "typecast" command objects
    if are_commands_adaptive_commands:
        command_objects: List[ChunkEncoder] = command_objects

    # values for a bitrate estimate in the progress bar
    encoded_frames_so_far = 0
    encoded_size_so_far = 0  # in kbps, kilo-bits per second
    if size_estimate_data is not None:
        encoded_frames_so_far, encoded_size_so_far = size_estimate_data

    total_scenes = len(command_objects)

    if use_celery:
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
        futures, completed_count = [], 0

        core_count, auto_scale = os.cpu_count(), multiprocess_workers == -1
        target_cpu_utilization, max_mem_usage = 95, 80

        max_jobs_limit = (
            core_count * 2
            if auto_scale
            else multiprocess_workers
            if multiprocess_workers != -1
            else core_count
        )

        local_jobs_limit = multiprocess_workers if not auto_scale else 2

        if throughput_scaling:
            local_jobs_limit = core_count / 2

        loop, executor = asyncio.get_event_loop(), ThreadPoolExecutor()

        # array of zeros to keep track of which cores are used, used for thread pinning with taskset
        used_cores = [0] * core_count

        frame_encoded_history: List[Tuple[int, float]] = []
        last_frame_encode = time.time()
        thughput_history = []

        current_thughput = -1
        previuus_thughput = -1
        thouput_compare = -1

        # -1 for decreasing, 0 for stable, 1 for increasing
        thouput_change_trend = 0
        thouput_reverse_trend_trigger_counter = 0

        def frames_encoded(frame_count=1):
            nonlocal last_frame_encode
            nonlocal frame_encoded_history
            nonlocal current_thughput
            nonlocal previuus_thughput
            nonlocal thughput_history
            now = time.time()
            if last_frame_encode == -1:
                last_frame_encode = now
            time_since_update = now - last_frame_encode
            last_frame_encode = now
            frame_encoded_history.append((frame_count, time_since_update))

            # measure the throughput based on the last 5 updates, save to history and print
            if len(frame_encoded_history) > 5:
                frame_encoded_history.pop(0)
            total_frames = sum([f[0] for f in frame_encoded_history])
            total_time = sum([f[1] for f in frame_encoded_history])
            thughput = total_frames / total_time
            thughput_history.append(thughput)
            # calculate the average throughput from the last 3 updates
            if len(thughput_history) > 3:
                thughput_history.pop(0)
            previuus_thughput = current_thughput
            current_thughput = sum(thughput_history) / len(thughput_history)
            # tqdm.write(
            #     f"Current throughput: {current_thughput:.2f} f/s, Last: {previuus_thughput:.2f} f/s, currently running jobs: {len(futures)}"
            # )

        def callback_wrapper():
            pbar.update()
            frames_encoded()

        # in the case that the encoder class supports "encoded a frame callback",
        # we can update the progress bar immediately after a frame is encoded,
        # so we set the callback
        if are_commands_adaptive_commands:
            for c in command_objects:
                c.encoded_a_frame_callback = (
                    lambda frame, bitrate, fps: callback_wrapper()
                )

        pbar.set_description(f"WORKERS: - CPU -% SWAP -%")

        while completed_count < total_scenes:
            currently_running_jobs = len(futures)

            # Start new jobs if we are under the local_jobs_limit
            while (
                currently_running_jobs <= local_jobs_limit
                and completed_count + currently_running_jobs < total_scenes
            ):
                command = command_objects[completed_count + currently_running_jobs]
                if pin_to_cores and 0 in used_cores:
                    core = used_cores.index(0)
                    used_cores[core] = 1
                    command.pin_to_core = core
                future = loop.run_in_executor(executor, command.run)
                futures.append(future)
                currently_running_jobs = len(futures)

            # wait for any of the tasks to finish
            done, pending = await asyncio.wait(futures, timeout=7)
            futures = [f for f in futures if not f.done()]
            currently_running_jobs = len(futures)

            # do stuff with the finished tasks
            for future in done:
                rslt = await future
                units_encoded = 1
                if are_commands_adaptive_commands and rslt is not None:
                    pined_core: int = rslt[0]
                    stats = rslt[1]
                    command_object = command_objects[completed_count]
                    if not command_object.supports_encoded_a_frame_callback():
                        units_encoded = command_object.chunk.get_frame_count()
                        frames_encoded(units_encoded)
                    if stats is not None:
                        encoded_frames_so_far += stats["length_frames"]
                        encoded_size_so_far += stats["size"]

                    if pin_to_cores:
                        used_cores[pined_core] = 0

                pbar.update(units_encoded)

                completed_count += 1

            # update the progress bar with the current system stats
            bitrate_estimate = " ESTM BITRATE N/A"
            if encoded_frames_so_far > 0:
                fps = command_objects[0].chunk.framerate
                bitrate_estimate = (
                    f" ESTM BITRATE {((encoded_size_so_far * 8) / (encoded_frames_so_far / fps)):.2f} "
                    f"kb/s"
                )
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            pbar.set_description(
                f"WORKERS {currently_running_jobs} CPU {int(cpu_percent)}% "
                f"MEM {int(memory_percent)}%{bitrate_estimate}"
            )
            # change the local_jobs_limit based on the picked strategy
            if throughput_scaling:
                if thouput_compare != current_thughput:
                    tqdm.write(
                        f"Checking throughput, current: {current_thughput:.2f} f/s, previous: {previuus_thughput:.2f} f/s"
                    )
                    # if we observe that throughput is decreasing, reverse the trend
                    if previuus_thughput > current_thughput:
                        thouput_reverse_trend_trigger_counter += 1
                        if thouput_reverse_trend_trigger_counter <= 2:
                            thouput_reverse_trend_trigger_counter = 0
                            if thouput_change_trend == -1:
                                thouput_change_trend = 1
                            elif thouput_change_trend == 1:
                                thouput_change_trend = -1
                            tqdm.write(
                                f"Reversing lobs limit trend to {'increasing' if thouput_change_trend == 1 else 'decreasing'}"
                            )
                            if thouput_change_trend == 1:
                                tqdm.write(
                                    f"Increasing local_jobs_limit to {local_jobs_limit + 1}"
                                )
                                local_jobs_limit += 1
                            # if the throughput is decreasing, decrease the local_jobs_limit
                            elif thouput_change_trend == -1:
                                tqdm.write(
                                    f"Decreasing local_jobs_limit to {local_jobs_limit - 1}"
                                )
                                local_jobs_limit -= 1

                            thouput_compare = current_thughput
            elif auto_scale and currently_running_jobs > 0:             
                local_jobs_limit += (
                    1
                    if cpu_percent <= target_cpu_utilization
                    and memory_percent <= max_mem_usage
                    else -1
                )
                local_jobs_limit = max(1, min(local_jobs_limit, max_jobs_limit))

            if finished_scene_callback is not None:
                finished_scene_callback(completed_count)

        pbar.close()
