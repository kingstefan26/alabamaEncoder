#!/usr/bin/python
import asyncio
import atexit
import os
import random
import sys
import time
from asyncio import Future
from concurrent.futures.thread import ThreadPoolExecutor

from tqdm import tqdm

from alabamaEncode.adaptive.analyser import do_adaptive_analasys
from alabamaEncode.adaptive.executor import AdaptiveCommand
from alabamaEncode.alabama import AlabamaContext, setup_context
from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.final_touches import (
    print_stats,
    generate_previews,
    create_torrent_file,
)
from alabamaEncode.parallelEncoding.CeleryApp import app, run_command_on_celery
from alabamaEncode.parallelEncoding.CeleryAutoscaler import Load
from alabamaEncode.parallelEncoding.Command import run_command
from alabamaEncode.parallelEncoding.worker import worker
from alabamaEncode.path import PathAlabama
from alabamaEncode.sceneSplit.VideoConcatenator import VideoConcatenator
from alabamaEncode.sceneSplit.chunk import ChunkSequence
from alabamaEncode.sceneSplit.split import get_video_scene_list_skinny

runtime = -1
runtime_file = ""


@atexit.register
def at_exit():
    global runtime
    global runtime_file
    if runtime != -1:
        current_session_runtime = time.time() - runtime

        saved_runtime = 0
        try:
            if os.path.exists(runtime_file):
                with open(runtime_file) as f:
                    saved_runtime = float(f.read())
        except:
            pass
        print(
            f"Current Session Runtime: {current_session_runtime}, Runtime From Previous Sessions: {saved_runtime}, Total Runtime: {current_session_runtime + saved_runtime}"
        )

        try:
            with open(runtime_file, "w") as f:
                f.write(str(current_session_runtime + saved_runtime))
        except:
            pass


async def process_chunks(
    sequence: ChunkSequence,
    ctx: AlabamaContext,
):
    command_objects = []

    for chunk in sequence.chunks:
        if not chunk.is_done():
            command_objects.append(AdaptiveCommand(ctx, chunk))

    # order chunks based on order
    if ctx.chunk_order == "random":
        random.shuffle(command_objects)
    elif ctx.chunk_order == "length_asc":
        command_objects.sort(key=lambda x: x.job.chunk.length)
    elif ctx.chunk_order == "length_desc":
        command_objects.sort(key=lambda x: x.job.chunk.length, reverse=True)
    elif ctx.chunk_order == "sequential":
        pass
    elif ctx.chunk_order == "sequential_reverse":
        command_objects.reverse()
    else:
        raise ValueError(f"Invalid chunk order: {ctx.chunk_order}")

    if len(command_objects) < 10:
        ctx.threads = os.cpu_count()

    print(f"Starting encoding of {len(command_objects)} scenes")

    await execute_commands(ctx.use_celery, command_objects, ctx.multiprocess_workers)


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
            run_command(command)

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


def get_lan_ip() -> str:
    """
    :return: the LAN ip
    """
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def clean_rate_probes(tempfolder: str):
    print("removing rate probe folders owo 🥺")
    for root, dirs, files in os.walk(tempfolder):
        # remove all folders that contain 'rate_probes'
        for name in dirs:
            if "rate_probes" in name:
                # remove {rate probe folder}/*.ivf
                for root2, dirs2, files2 in os.walk(tempfolder + name):
                    for name2 in files2:
                        if name2.endswith(".ivf"):
                            try:
                                os.remove(tempfolder + name + "/" + name2)
                            except:
                                pass
        # remove all *.stat files in tempfolder
        for name in files:
            if name.endswith(".stat"):
                # try to remove
                try:
                    os.remove(tempfolder + name)
                except:
                    pass

    # clean empty folders in the temp folder
    for root, dirs, files in os.walk(tempfolder):
        for name in dirs:
            if len(os.listdir(os.path.join(root, name))) == 0:
                os.rmdir(os.path.join(root, name))


def main():
    """
    Main entry point
    """
    global runtime
    runtime = time.time()

    # if a user does 'python __main__.py clear' then clear the celery queue
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        print("Clearing celery queue")
        app.control.purge()
        quit()

    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker()

    config: AlabamaContext = setup_context()

    global runtime_file
    runtime_file = config.temp_folder + "runtime.txt"

    if config.use_celery:
        host_address = get_lan_ip()
        print(f"Got lan ip: {host_address}")
        num_workers = app.control.inspect().active_queues()
        if num_workers is None:
            print("No workers detected, please start some")
            quit()
        print(f"Number of available workers: {len(num_workers)}")
    else:
        print("Using multiprocessing instead of celery")

    clean_rate_probes(config.temp_folder)

    chunks_sequence: ChunkSequence = get_video_scene_list_skinny(
        input_file=config.input_file,
        cache_file_path=config.temp_folder + "sceneCache.pt",
        max_scene_length=config.max_scene_length,
        start_offset=config.start_offset,
        end_offset=config.end_offset,
        override_bad_wrong_cache_path=config.override_scenecache_path_check,
    )

    chunks_sequence.setup_paths(
        config.temp_folder, config.get_encoder().get_chunk_file_extension()
    )

    if not os.path.exists(config.output_file):
        do_adaptive_analasys(chunks_sequence, config)

        iter_counter = 0

        if config.dry_run:
            iter_counter = 2

        while chunks_sequence.sequence_integrity_check() is True:
            iter_counter += 1
            if iter_counter > 3:
                print("Integrity check failed 3 times, aborting")
                quit()

            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(
                    process_chunks(
                        chunks_sequence,
                        config,
                    )
                )
            except KeyboardInterrupt:
                print("Keyboard interrupt, stopping")
                quit()
            finally:
                loop.stop()

        try:
            concat = VideoConcatenator(
                output=config.output_file,
                file_with_audio=config.input_file,
                audio_param_override=config.audio_params,
                start_offset=config.start_offset,
                end_offset=config.end_offset,
                title=config.title,
                encoder_name=config.encoder_name,
                mux_audio=config.encode_audio,
            )
            concat.find_files_in_dir(
                folder_path=config.temp_folder,
                extension=config.get_encoder().get_chunk_file_extension(),
            )
            concat.concat_videos()
        except Exception as e:
            print("Concat at the end failed 😷")
            raise e
    else:
        print("Output file exists 🤑, printing stats")

    print_stats(
        output_folder=config.output_folder,
        output=config.output_file,
        config_bitrate=config.bitrate,
        input_file=config.raw_input_file,
        grain_synth=-1,
        title=config.title,
        cut_intro=(True if config.start_offset > 0 else False),
        cut_credits=(True if config.end_offset > 0 else False),
        croped=(True if config.crop_string != "" else False),
        scaled=(True if config.scale_string != "" else False),
        tonemaped=(
            True
            if not config.hdr and Ffmpeg.is_hdr(PathAlabama(config.input_file))
            else False
        ),
    )
    if config.generate_previews:
        print("Generating previews")
        generate_previews(
            input_file=config.output_file,
            output_folder=config.output_folder,
            num_previews=4,
            preview_length=5,
        )
        create_torrent_file(
            video=config.output_file,
            encoder_name=config.encoder_name,
            output_folder=config.output_folder,
        )
    clean_rate_probes(config.temp_folder)
    quit()


if __name__ == "__main__":
    main()
