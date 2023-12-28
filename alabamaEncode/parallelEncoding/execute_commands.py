import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import psutil
from tqdm import tqdm

from alabamaEncode.adaptive.executor import AdaptiveCommand
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.parallelEncoding.CeleryApp import run_command_on_celery, app


async def execute_commands(
    use_celery,
    command_objects,
    multiprocess_workers,
    override_sequential=True,
    pin_to_cores=False,
    finished_scene_callback=None,
):
    """
    Execute a list of commands in parallel
    :param pin_to_cores:
    :param use_celery: execute on a celery cluster
    :param command_objects: objects with a `run()` method to execute
    :param multiprocess_workers: number of workers in multiprocess mode, -1 for auto adjust
    :param override_sequential: if true, will run sequentially if there is less than 10 scenes
    :param finished_scene_callback: call when a scene finishes, contains the number of finished scenes
    """
    # if len(command_objects) < 10 and override_sequential == True:
    #     print("Less than 10 scenes, running encodes sequentially")
    #
    #     for command in command_objects:
    #         command.run()
    #
    # elif use_celery:
    are_commands_adaptive_commands = isinstance(command_objects[0], AdaptiveCommand)
    if use_celery:
        is_adaptive_command = are_commands_adaptive_commands
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

        # to provide a bitrate estimate in the progress bar
        encoded_frames_so_far = 0
        encoded_size_so_far = 0  # in kbits

        concurrent_jobs_limit = multiprocess_workers if not auto_scale else 2

        loop, executor = asyncio.get_event_loop(), ThreadPoolExecutor()

        used_cores = [0] * core_count

        total_frames = (
            sum([c.chunk.get_frame_count() for c in command_objects])
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

            done, pending = await asyncio.wait(futures, timeout=5)
            futures = [f for f in futures if not f.done()]

            for future in done:
                w = await future
                pined_core: int = w[0]
                stats: EncodeStats = w[1]
                if (
                    are_commands_adaptive_commands
                    and not command_objects[0].supports_encoded_a_frame_callback()
                ):
                    pbar.update(
                        command_objects[completed_count].chunk.get_frame_count()
                    )
                else:
                    pbar.update()

                encoded_frames_so_far += stats.length_frames
                encoded_size_so_far += stats.size

                if pin_to_cores:
                    used_cores[pined_core] = 0
                completed_count += 1

            cpu_utilization = psutil.cpu_percent()
            mem_usage = psutil.virtual_memory().percent
            bitrate_estimate = "ESTM BITRATE N/A"
            if encoded_frames_so_far > 0:
                bitrate_estimate = f"ESTM BITRATE {(encoded_frames_so_far / encoded_size_so_far) * 1000:.2f} kb/s"
            pbar.set_description(
                f"WORKERS {len(futures)} CPU {int(cpu_utilization)}% "
                f"MEM {int(mem_usage)}% {bitrate_estimate}"
            )

            if auto_scale and len(futures) > 0:
                concurrent_jobs_limit += (
                    1
                    if cpu_utilization < target_cpu_utilization
                    and mem_usage < max_mem_usage
                    else -1
                )
                concurrent_jobs_limit = max(1, min(concurrent_jobs_limit, max_limit))

            if finished_scene_callback is not None:
                finished_scene_callback(completed_count)

        pbar.close()
