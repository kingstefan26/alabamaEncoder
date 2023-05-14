#!/usr/bin/python
import argparse
import asyncio
import glob
import json
import os
import random
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from multiprocessing.pool import ThreadPool

from tqdm import tqdm

from hoeEncode.CeleryApp import app, run_command_on_celery
from hoeEncode.CeleryAutoscaler import Load
from hoeEncode.adaptiveEncoding.adaptiveAnalyser import do_adaptive_analasys
from hoeEncode.adaptiveEncoding.adaptiveCommand import AdaptiveCommand
from hoeEncode.encoders.AbstractEncoderCommand import EncoderKommand
from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import check_for_invalid, get_frame_count, do_cropdetect, doesBinaryExist
from hoeEncode.parallelEncoding.Command import run_command
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.Chunks import ChunkSequence
from hoeEncode.sceneSplit.VideoConcatenator import VideoConcatenator
from hoeEncode.sceneSplit.split import get_video_scene_list_skinny
from hoeEncode.utils.execute import syscmd


async def cancel_all_tasks():
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    print('App quiting. if you arent finished, resume by reruning the script with the same settings')
    await asyncio.gather(*tasks, return_exceptions=True)


def at_exit(loop):
    loop.create_task(cancel_all_tasks())


async def process_chunks(chunk_list: ChunkSequence, encdr_config: EncoderConfigObject, celeryless_encoding: bool,
                         multiprocess_workers: int, chunk_order='sequential'):
    command_objects = []

    for chunk in tqdm(chunk_list.chunks, desc='Preparing scenes', unit='scene'):
        job = EncoderJob(chunk)

        if not os.path.exists(job.chunk.chunk_path):
            if encdr_config.convexhull:
                obj = AdaptiveCommand()
            else:
                obj = EncoderKommand(AbstractEncoderSvtenc())

            obj.setup(job, encdr_config)
            command_objects.append(obj)

    # order chunks based on order
    if chunk_order == 'random':
        random.shuffle(command_objects)
    elif chunk_order == 'length_asc':
        command_objects.sort(key=lambda x: x.job.chunk.length)
    elif chunk_order == 'length_desc':
        command_objects.sort(key=lambda x: x.job.chunk.length, reverse=True)
    elif chunk_order == 'sequential':
        pass
    else:
        raise ValueError(f'Invalid chunk order: {chunk_order}')

    if len(command_objects) < 10:
        encdr_config.threads = os.cpu_count()

    print(f'Starting encoding of {len(command_objects)} scenes')

    if encdr_config.dry_run:
        for command in command_objects:
            print(command.get_dry_run())

    elif len(command_objects) < 10:
        print('Less than 10 scenes, running encodes sequentially')

        for command in command_objects:
            run_command(command)

    elif celeryless_encoding:

        total_scenes = len(command_objects)
        futures = []
        completed_count = 0

        load = Load()
        target_cpu_utilization = 1.1
        cpu_threshold = 0.3
        max_concurrent_jobs = os.cpu_count()  # Initial value to be adjusted dynamically
        if multiprocess_workers != -1:
            max_concurrent_jobs = multiprocess_workers

        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor()

        with tqdm(total=total_scenes, desc='Encoding', unit='scene', dynamic_ncols=True) as pbar:
            while completed_count < total_scenes:
                # Start new tasks if there are available slots
                while len(futures) < max_concurrent_jobs and completed_count + len(futures) < total_scenes:
                    command = command_objects[completed_count + len(futures)]
                    futures.append(
                        loop.run_in_executor(
                            executor,
                            command.run
                        )
                    )

                # Wait for any task to complete
                done, _ = await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)

                # Process completed tasks
                for future in done:
                    result = await future
                    # do something with the result
                    pbar.update()
                    completed_count += 1

                # Remove completed tasks from the future list
                futures = [future for future in futures if not future.done()]

                if multiprocess_workers == -1:
                    # Check CPU utilization and adjust max_concurrent_jobs if needed
                    cpu_utilization = load.get_load()
                    new_max = max_concurrent_jobs
                    if cpu_utilization < target_cpu_utilization:
                        new_max += 1
                    elif cpu_utilization > target_cpu_utilization + cpu_threshold:
                        new_max -= 1

                    # Adjust max_concurrent_jobs within defined bounds
                    new_max = max(1, new_max)
                    if new_max != max_concurrent_jobs:
                        max_concurrent_jobs = new_max
                        tqdm.write(
                            f"CPU load: {(cpu_utilization * 100):.2f}%, adjusting workers to {max_concurrent_jobs} "
                        )
    else:
        for a in command_objects:
            a.run_on_celery = True

        results = []
        with tqdm(total=len(command_objects), desc='Encoding', unit='scene', dynamic_ncols=True) as pbar:
            for command in command_objects:
                result = run_command_on_celery.delay(command)

                results.append(result)

            while True:
                num_workers = len(app.control.inspect().active_queues())
                if num_workers < 0:
                    print('No workers available, waiting for workers to become available')
                if all(result.ready() for result in results):
                    break
                for result in results:
                    if result.ready():
                        pbar.update()
                        results.remove(result)


def get_lan_ip() -> str:
    """
    :return: the LAN ip
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def clean_rate_probes(tempfolder: str):
    print('removing rate probe folders owo 🥺')
    for root, dirs, files in os.walk(tempfolder):
        # remove all folders that contain 'rate_probes'
        for name in dirs:
            if 'rate_probes' in name:
                # remove {rate probe folder}/*.ivf
                for root2, dirs2, files2 in os.walk(tempfolder + name):
                    for name2 in files2:
                        if name2.endswith('.ivf'):
                            try:
                                os.remove(tempfolder + name + '/' + name2)
                            except:
                                pass
        # remove all *.stat files in tempfolder
        for name in files:
            if name.endswith('.stat'):
                # try to remove
                try:
                    os.remove(tempfolder + name)
                except:
                    pass


def check_chunk(c: ChunkObject):
    c.chunk_done = False
    if not os.path.exists(c.chunk_path):
        return None

    if check_for_invalid(c.chunk_path):
        tqdm.write(f'chunk {c.chunk_path} failed the ffmpeg integrity check 🤕')
        return c.chunk_path

    actual_frame_count = get_frame_count(c.chunk_path)
    expected_frame_count = c.last_frame_index - c.first_frame_index

    if actual_frame_count != expected_frame_count:
        return c.chunk_path

    c.chunk_done = True

    return None


def process_chunk(args):
    c, pbar = args
    result = check_chunk(c)
    pbar.update()
    return result


def integrity_check(seq: ChunkSequence, temp_folder: str) -> bool:
    """
    checks the integrity of the chunks, and removes any that are invalid, remove probe folders, and see if all are done
    :param temp_folder:
    :param seq: all the scenes to check
    :return: true if there are broken chunks
    """

    print('Preforming integrity check 🥰')
    seq_chunks = list(seq.chunks)
    total_chunks = len(seq_chunks)

    with tqdm(total=total_chunks, desc="Checking files", unit='file') as pbar:
        with ThreadPool(5) as pool:
            chunk_args = [(c, pbar) for c in seq_chunks]
            invalid_chunks = list(pool.imap(process_chunk, chunk_args))

    invalid_chunks = [chunk for chunk in invalid_chunks if chunk is not None]

    if len(invalid_chunks) > 0:
        print(f'Found {len(invalid_chunks)} invalid files, removing them 😂')
        for c in invalid_chunks:
            os.remove(c)
        clean_rate_probes(temp_folder)
        return True

    # count chunks that are not done
    not_done = len([c for c in seq.chunks if not c.chunk_done])

    if not_done > 0:
        print(f'Only {len(seq.chunks) - not_done}/{len(seq.chunks)} chunks are done 😏')
        clean_rate_probes(temp_folder)
        return True

    print('All chunks passed integrity checks 🤓')
    return False


def main():
    """
    Main entry point
    """
    # if a user does 'python __main__.py clear' then clear the celery queue
    if len(sys.argv) > 1 and sys.argv[1] == 'clear':
        print('Clearing celery queue')
        app.control.purge()
        quit()

    parser = argparse.ArgumentParser(description='Encode a video using SVT-AV1, and mux it with ffmpeg')
    parser.add_argument('input', type=str, help='Input video file')
    parser.add_argument('output', type=str, help='Output video file')
    parser.add_argument('temp_dir', help='Temp directory', nargs='?', default='temp/', type=str, metavar='temp_dir')
    parser.add_argument('--audio', help='Mux audio', action='store_true', default=True)
    parser.add_argument('--audio_params', help='Audio params', type=str,
                        default='-c:a libopus -ac 2 -b:v 96k -vbr on -lfe_mix_level 0.5 -mapping_family 1')
    parser.add_argument('--celery', help='Encode on a celery cluster, that is at localhost', action='store_true',
                        default=False)
    parser.add_argument('--dry', help='Dry run, dont actually encode', action='store_true', default=False)
    parser.add_argument('--autocrop', help='Automatically crop the video', action='store_true')
    parser.add_argument('--crop_override', type=str, default='',
                        help='Override the crop, put your vf ffmpeg there, example '
                             'scale=-2:1080:flags=lanczos,zscale=t=linear...'
                             ' just make sure ffmpeg on all workers has support')
    parser.add_argument('--bitrate', help='Bitrate to use, ignored if using auto bitrate ladder', type=str,
                        default='2000k')
    parser.add_argument('--autobitrate', help='Enable automatic bitrate optimisation per chunk', action='store_true',
                        default=False)
    parser.add_argument('--multiprocess_workers',
                        help='Number of workers to use for multiprocessing, if -1 the progran will auto scale',
                        type=int,
                        default=-1)
    parser.add_argument('--ssim-db-target', type=float, default=20,
                        help='What ssim dB to target when using auto bitrate,'
                             ' 22 is pretty lossless, generally recommend 21, 20 lowkey blurry,'
                             ' bellow 19.5 is bad')

    parser.add_argument('--autograin', help="Automagicly pick grainsynth value", action='store_true', default=False)

    parser.add_argument('--grain_override', help="Manually give the grainsynth value, 0 to disable", type=int,
                        default=7, choices=range(0, 63))

    parser.add_argument('--autoparam', help='Automagicly chose params', action='store_true', default=True)

    parser.add_argument('--auto_bitrate_ladder', help='Automatically chose bitrate based on quality',
                        action='store_true', default=False)
    parser.add_argument('--vmaf_target', help='What vmaf to target when using autobitrate ladder', default=96)

    parser.add_argument('--max_scene_length', help="If a scene is longer then this, it will recursively cut in the"
                                                   " middle it to get until each chunk is within the max", type=int,
                        default=10, metavar='max_scene_length')
    parser.add_argument('--auto_crf', help='Alternative to auto bitrate tuning, that uses crf', action='store_true',
                        default=False)
    # encode chunks oerder, possbile values: 'random', 'sequential', 'length_desc', 'length_asc'
    parser.add_argument('--chunk_order', help='Encode chunks in a specific order', type=str, default='sequential',
                        choices=['random', 'sequential', 'length_desc', 'length_asc'])

    parser.add_argument('--from',
                        help='Offset from the beginning of the video (in seconds), useful for cutting intros etc',
                        default=-1)
    parser.add_argument('--to',
                        help='Offset from the end of the video (in seconds), useful for cutting end credits outtros etc',
                        default=-1)

    args = parser.parse_args()

    input_path = args.input

    # check if input is an absolute path
    if input_path[0] != '/':
        print('Input video is not absolute, please use absolute paths')

    if args.autograin and not doesBinaryExist('butteraugli'):
        print('Autograin requires butteraugli in path, please install it')
        quit()

    host_adrees = get_lan_ip()
    print(f'Got lan ip: {host_adrees}')

    # turn tempfolder into a full path
    tempfolder = os.path.abspath(args.temp_dir) + '/'
    input_file = tempfolder + 'temp.mkv'

    dont_use_celery = False if args.celery else True

    if args.dry and not dont_use_celery:
        print('Dryrun can only work locally using multiprocessing mode')
        quit()

    if not dont_use_celery:
        num_workers = app.control.inspect().active_queues()
        print(f'Number of available workers: {len(num_workers)}')
    else:
        print('Using multiprocessing instead of celery')

    if not os.path.exists(tempfolder):
        os.mkdir(tempfolder)
    else:
        syscmd(f'rm {tempfolder}*.log')

    # copy input file to temp folder
    if not os.path.exists(input_file):
        os.system(f'ln -s "{input_path}" "{input_file}"')

    # example: crop=3840:1600:0:280,scale=1920:800:flags=lanczos
    croppy_floppy = args.crop_override
    if args.autocrop and croppy_floppy == '':
        cropdetect = do_cropdetect(ChunkObject(path=input_file))
        if cropdetect != '':
            croppy_floppy = f'crop={cropdetect}'

    scenes_skinny: ChunkSequence = get_video_scene_list_skinny(input_file=input_file,
                                                               cache_file_path=tempfolder + 'sceneCache.pt',
                                                               max_scene_length=args.max_scene_length)
    for xyz in scenes_skinny.chunks:
        xyz.chunk_path = f'{tempfolder}{xyz.chunk_index}.ivf'

    config = EncoderConfigObject(crop_string=croppy_floppy, convexhull=args.autobitrate, temp_folder=tempfolder,
                                 server_ip=host_adrees, remote_path=tempfolder, dry_run=args.dry,
                                 ssim_db_target=args.ssim_db_target, passes=3, vmaf=args.vmaf_target, speed=4)
    config.crf_bitrate_mode = args.auto_crf
    try:
        config.bitrate = int(args.bitrate[:-1])
    except ValueError:
        raise ValueError('Bitrate must be in k\'s, example: 2000k')

    config.grain_synth = args.grain_override

    config = do_adaptive_analasys(scenes_skinny, config, do_grain=args.autograin,
                                  do_bitrate_ladder=args.auto_bitrate_ladder, do_qm=args.autoparam)
    # if config.grain_synth > 8 or config.bitrate < 1400:
    #     print('Turning off grain denoise because bitrate is too low')
    #     config.film_grain_denoise = 0

    if config.grain_synth == 0 and config.bitrate < 2000:
        print('Film grain less then 0 and bitrate is low, overriding to 2 film grain')
        config.film_grain = 2

    iter_counter = 0
    while integrity_check(scenes_skinny, tempfolder) is True:
        iter_counter += 1
        if iter_counter > 3:
            print('Integrity check failed 3 times, aborting')
            quit()
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(process_chunks(scenes_skinny, config, celeryless_encoding=dont_use_celery,
                                                   multiprocess_workers=args.multiprocess_workers,
                                                   chunk_order=args.chunk_order))
        finally:
            at_exit(loop)
            loop.close()

    # if we are doing a dry run the process, chunks will spit out the commands, so we quit here
    if args.dry:
        quit()

    try:
        concat = VideoConcatenator(output=args.output, file_with_audio=input_file,
                                   audio_param_override=args.audio_params)
        concat.find_files_in_dir(folder_path=tempfolder, extension='.ivf')
        concat.concat_videos()
    except:
        print('Concat at the end failed sobbing 😷')
        quit()

    # Load all ./temp/stats/*.json object
    stats = []
    for file in glob.glob(f'{tempfolder}stats/*.json'):
        with open(file) as f:
            stats.append(json.load(f))

    # sum up all the time_encoding variables
    time_encoding = 0
    for stat in stats:
        time_encoding += stat['time_encoding']

    print(f'Total encoding time across chunks: {time_encoding} seconds')

    # get the worst/best/med target_miss_proc
    target_miss_proc = []
    for stat in stats:
        # turn the string into a float then round to two places
        target_miss_proc.append(round(float(stat['target_miss_proc']), 2))
    target_miss_proc.sort()
    print(f'Worst target_miss_proc: {target_miss_proc[-1]}')
    print(f'Best target_miss_proc: {target_miss_proc[0]}')
    print(f'Median target_miss_proc: {target_miss_proc[int(len(target_miss_proc) / 2)]}')


if __name__ == "__main__":
    main()
