#!/usr/bin/python
import argparse
import atexit
import logging
import os
import shutil
import sys
from typing import Any

from tqdm import tqdm
from tqdm.contrib.concurrent import process_map

from CeleryApp import app
from hoeEncode.bitrateAdapt.AutoBitrate import ConvexEncoder
from hoeEncode.bitrateAdapt.AutoGrain import get_best_avg_grainsynth
from hoeEncode.encoders.AbstractEncoderCommand import EncoderKommand
from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import check_for_invalid, get_frame_count, do_cropdetect, doesBinaryExist
from hoeEncode.utils.execute import syscmd
from hoeEncode.parallelEncoding.Command import run_command
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.Chunks import ChunkSequence
from hoeEncode.sceneSplit.VideoConcatenator import VideoConcatenator
from hoeEncode.sceneSplit.split import get_video_scene_list_skinny
from paraliezeMeHoe.ThaVaidioEncoda import run_command_on_celery

tasks = []


def exit_message():
    for task in tasks:
        task.abort()
    print('App quiting. if you arent finished, resume by reruning the script with the same settings')


atexit.register(exit_message)


def process_chunks(chunk_list: ChunkSequence,
                   encdr_config: EncoderConfigObject,
                   celeryless_encoding: bool,
                   multiprocess_workers: int):
    command_objects = []



    for chunk in tqdm(chunk_list.chunks, desc='Preparing scenes', unit='scene'):
        job = EncoderJob(chunk)

        if not os.path.exists(job.chunk.chunk_path):
            if encdr_config.convexhull:
                obj = ConvexEncoder()
            else:
                obj = EncoderKommand(AbstractEncoderSvtenc())

            obj.setup(job, encdr_config)
            command_objects.append(obj)

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
        process_map(run_command,
                    command_objects,
                    max_workers=multiprocess_workers,
                    chunksize=1,
                    desc='Encoding',
                    unit='scene')
    else:
        results = []
        with tqdm(total=len(command_objects), desc='Encoding', unit='scene') as pbar:
            for command in command_objects:
                # task = run_command_on_celery.s(command)
                # result = task.apply_async()

                result = run_command_on_celery.delay(command)

                results.append(result)
                tasks.append(result)

            while True:
                if all(result.ready() for result in results):
                    break
                for result in results:
                    if result.ready():
                        pbar.update()
                        results.remove(result)


def get_lan_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def clean_rate_probes():
    print('removing rate probe folders owo 🥺')
    for root, dirs, files in os.walk(tempfolder):
        # remove all folders that contain 'rate_probes'
        for name in dirs:
            if 'rate_probes' in name:
                shutil.rmtree(tempfolder + name)


def integrity_check(seq: ChunkSequence) -> bool:
    """
    checks the integrity of the chunks, and removes any that are invalid, remove probe folders, and see if all are done
    :param seq: all the scenes to check
    :return: true if there are broken chunks
    """

    print('Preforming integrity check 🥰')

    invalid_chunks = []

    for c in tqdm(seq.chunks, desc="Checking files", unit='file'):
        c.chunk_done = False
        if not os.path.exists(c.chunk_path):
            continue

        if check_for_invalid(c.chunk_path):
            tqdm.write(f'chunk {c.chunk_path} failed the ffmpeg integrity check 🤕')
            invalid_chunks.append(c.chunk_path)
            continue

        actual_frame_count = get_frame_count(c.chunk_path)
        expected_frame_count = c.last_frame_index - c.first_frame_index

        # if the frame count is not the same as the chunk length, then the file is invalid
        if actual_frame_count != expected_frame_count:
            invalid_chunks.append(c.chunk_path)
            tqdm.write(f'chunk {c.chunk_path} has failed the frame count check,'
                       f' expected {expected_frame_count} frames, got {actual_frame_count} frames 🥶')

        c.chunk_done = True

    if len(invalid_chunks) > 0:
        print(f'Found {len(invalid_chunks)} invalid files, removing them 😂')
        for c in invalid_chunks:
            os.remove(c)
        clean_rate_probes()
        return True

    # count chunks that are not done
    not_done = len([c for c in seq.chunks if not c.chunk_done])

    if not_done > 0:
        print(f'Only {len(seq.chunks) - not_done}/{len(seq.chunks)} chunks are done 😏')
        clean_rate_probes()
        return True

    print('All chunks passed integrity checks 🤓')
    return False


if __name__ == "__main__":

    # if a user does 'python main.py clear' then clear the celery queue
    if len(sys.argv) > 1 and sys.argv[1] == 'clear':
        print('Clearing celery queue')
        app.control.purge()
        quit()

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Encode a video using SVT-AV1, and mux it with ffmpeg')
    parser.add_argument('input', type=str, help='Input video file')
    parser.add_argument('output', type=str, help='Output video file')
    parser.add_argument('temp_dir', help='Temp directory', nargs='?', default='temp/', type=str, metavar='temp_dir')
    parser.add_argument('--audio', help='Mux audio', action='store_true', default=True)
    parser.add_argument('--audio_params', help='Audio params', type=str,
                        default='-c:a libopus -ac 2 -b:v 96k -vbr on -lfe_mix_level 0.5')
    parser.add_argument('--celeryless', help='Encode without celery', action='store_true', default=False)
    parser.add_argument('--dry', help='Dry run, dont actually encode', action='store_true', default=False)
    parser.add_argument('--autocrop', help='Automatically crop the video', action='store_true')
    parser.add_argument('--crop_override', type=str, default='',
                        help='Override the crop, put your vf ffmpeg there, example '
                             'scale=-2:1080:flags=lanczos,zscale=t=linear etc...'
                             ' just make sure ffmpeg on all workers has support')
    parser.add_argument('--mux', help='Mux the video and audio together', action='store_true', default=False)
    parser.add_argument('--integrity_check', help='Check for intergrity of encoded files', action='store_true',
                        default=True)
    parser.add_argument('--bitrate', help='Bitrate to use', type=str, default='2000k')
    parser.add_argument('--autobitrate', help='Enable automatic bitrate optimisation', action='store_true',
                        default=False)
    parser.add_argument('--multiprocess_workers', help='Number of workers to use for multiprocessing', type=int,
                        default=7)
    parser.add_argument('--ssim-db-target', type=float, default=20,
                        help='What ssim dB to target when using auto bitrate,'
                             ' 22 is pretty lossless, generally recommend 21, 20 lowkey blurry,'
                             ' bellow 19.5 is bad')

    # auto grain
    parser.add_argument('--autograin', help="Automagicly pick grainsynth value", action='store_true', default=False)

    # grain override
    parser.add_argument('--grainsynth', help="Manually give the grainsynth value, 0 to disable", type=int, default=7,
                        choices=range(0, 63))

    parser.add_argument('--max-scene-length', help="If a scene is longer then this, it will recursively cut in the"
                                                   " middle it to get until each chunk is within the max",
                        type=int, default=10, metavar='max_scene_length')

    args = parser.parse_args()

    input_path = args.input

    # check if input is an absolute path
    if input_path[0] != '/':
        print('Input video is not absolute, please use absolute paths')

    if args.autograin and not doesBinaryExist('butteraugli'):
        print('Autograin requires butteraugli in path, please install it')
        quit()

    # do auto bitrate ladder 😍 sometime maybe
    bitraten = args.bitrate

    # usually the local network ip of the machine running the host
    host_adrees = get_lan_ip()
    print(f'Got lan ip: {host_adrees}')

    # if true, the script will not actually encode the chunks, just print the commands
    dry_run = args.dry

    tempfolder = args.temp_dir
    # turn tempfolder into a full path
    tempfolder = os.path.abspath(tempfolder) + '/'
    input_file: str | Any = tempfolder + 'temp.mkv'

    DontUseCelery = args.celeryless

    if dry_run and not DontUseCelery:
        print('Dryrun can only work locally using multiprocessing mode')
        quit()

    if not DontUseCelery:
        with app.connection() as connection:
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
        os.system(f'cp "{input_path}" "{input_file}"')

    # example: crop=3840:1600:0:280,scale=1920:800:flags=lanczos
    croppy_floppy = args.crop_override
    if args.autocrop and croppy_floppy == '':
        cropdetect = do_cropdetect(ChunkObject(path=input_file))
        if cropdetect != '':
            croppy_floppy = f'-vf "crop={cropdetect}"'

    scenes_skinny: ChunkSequence = get_video_scene_list_skinny(input_file=input_file,
                                                               cache_file_path=tempfolder + 'sceneCache.pt',
                                                               max_scene_length=args.max_scene_length)
    for xyz in scenes_skinny.chunks:
        xyz.chunk_path = f'{tempfolder}{xyz.chunk_index}.ivf'

    config = EncoderConfigObject(two_pass=True,
                                 crop_string=croppy_floppy,
                                 convexhull=args.autobitrate,
                                 temp_folder=tempfolder,
                                 server_ip=host_adrees,
                                 remote_path=tempfolder,
                                 dry_run=dry_run,
                                 ssim_db_target=args.ssim_db_target)
    try:
        config.bitrate = int(bitraten[:-1])
    except ValueError:
        raise ValueError('Bitrate must be in k\'s, example: 2000k')

    if args.autograin:
        config.grain_synth = get_best_avg_grainsynth(input_file=input_file,
                                                     scenes=scenes_skinny,
                                                     temp_folder=tempfolder,
                                                     cache_filename=tempfolder + 'ideal_grain.pt')
    else:
        config.grain_synth = args.grainsynth

    if args.integrity_check:
        iter_counter = 0
        while integrity_check(scenes_skinny) is True:
            iter_counter += 1
            if iter_counter > 3:
                print('Integrity check failed 3 times, aborting')
                quit()
            process_chunks(scenes_skinny, config, celeryless_encoding=DontUseCelery,
                           multiprocess_workers=args.multiprocess_workers)
    else:
        print('WARNING: integrity check is disabled, this is not recommended')
        process_chunks(scenes_skinny, config, celeryless_encoding=DontUseCelery,
                       multiprocess_workers=args.multiprocess_workers)

    # if we are doing a dry run the process, chunks will spit out the commands, so we quit here
    if dry_run:
        quit()

    mux_at_the_end = args.mux
    mux_output = args.output
    mux_audio = args.audio

    try:
        concat = VideoConcatenator(output=mux_output,
                                   file_with_audio=input_file,
                                   audio_param_override=args.audio_params)
        concat.find_files_in_dir(folder_path=tempfolder, extension='.ivf')
        concat.concat_videos()
    except Exception as e:
        print('Concat at the end failed sobbing 😷')
        quit()
