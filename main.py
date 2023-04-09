import argparse
import atexit
import logging
import os
import shutil
import sys
import tempfile
from typing import List

from tqdm import tqdm
from tqdm.contrib.concurrent import process_map

from CeleryApp import app
from hoeEncode.ConvexHullEncoding.AutoGrain import get_best_avg_grainsynth
from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, syscmd, do_cropdetect, get_frame_count, \
    check_for_invalid, EncoderJob
from hoeEncode.split.split import get_video_scene_list
from paraliezeMeHoe.ThaVaidioEncoda import gen_svt_kummands, \
    run_kummand, run_kummad_on_celery, convex_svt

tasks = []


def exit_message():
    # call task.abort() on all tasks
    for task in tasks:
        task.abort()
    print('App quiting. if you arent finished, resume by reruning the script with the same settings')


atexit.register(exit_message)


def process_chunks(scenes: List[List[int]],
                   inputfile: str,
                   encdr_config: EncoderConfigObject,
                   celeryless_encoding: bool,
                   multiprocess_workers: int):
    kumandobjects = []
    for i, frag in tqdm(enumerate(scenes), desc='Preparing scenes', unit='scene'):
        chunk = ChunkObject(path=inputfile, first_frame_index=(frag[0]), last_frame_index=(frag[1]))
        ivf = f"{tempfolder}{i}.ivf"
        job = EncoderJob(chunk, i, ivf)

        if not os.path.exists(ivf):
            if encdr_config.convexhull:
                kummnad_object = convex_svt(job, encdr_config)
            else:
                kummnad_object = gen_svt_kummands(job, encdr_config)

            kumandobjects.append(kummnad_object)

    print('Starting encoding of ' + str(len(kumandobjects)) + ' scenes')

    if encdr_config.dry_run:
        for kummand in kumandobjects:
            print(kummand.get_dry_run())
        return

    if celeryless_encoding:
        process_map(run_kummand,
                    kumandobjects,
                    max_workers=multiprocess_workers,
                    chunksize=1,
                    desc='Encoding SVT-AV1',
                    unit="scene")
    else:
        results = []
        with tqdm(total=len(kumandobjects), desc='Encoding SVT-AV1', unit='scene') as pbar:
            for cvm in kumandobjects:
                task = run_kummad_on_celery.s(cvm)
                result = task.apply_async()
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


def integrity_check(tempfolder, fragments):
    # create a array of all files, so we can tqdm
    ivf_files = []
    for root, dirs, files in os.walk(tempfolder):
        for name in files:
            if name.endswith('.ivf'):
                ivf_files.append(name)

    # check every chunk and verify that 1: it's not corrupted 2: its length is correct
    # if not, prompt the user with a command to remove them
    invalid_chunks = []
    # os.walk on the temp dir and add a line for every ivf file
    for name in tqdm(ivf_files, desc="Checking files"):
        # get the file name
        name = name[:-4]  # 1.ivf -> 1
        file_full_path = tempfolder + name + '.ivf'

        if check_for_invalid(file_full_path):
            invalid_chunks.append(file_full_path)
            tqdm.write(f'chunk {file_full_path} failed the ffmpeg integrity check')
            continue

        matching_frag = None

        # get the matching chunk
        for i, frag in enumerate(fragments):
            if i == int(name):
                matching_frag = frag
                break

        if matching_frag is None:
            raise Exception('Could not find matching chunk for file ' + file_full_path)

        # get the frame count
        frame_count = get_frame_count(file_full_path)
        # get the length of the chunk
        chunk_length = matching_frag[1] - matching_frag[0]
        # if the frame count is not the same as the chunk length, then the file is invalid
        if frame_count != chunk_length:
            invalid_chunks.append(file_full_path)
            tqdm.write(f'chunk {file_full_path} has failed the frame count check, expected {chunk_length} frames,'
                       f'got {frame_count} frames')

    if len(invalid_chunks) > 0:
        print('The following chunks are invalid:')
        for chunk in invalid_chunks:
            print(chunk)
        print('Please remove them and rerun the script, command to remove them:')

        command = 'rm '
        for chunk in invalid_chunks:
            command += chunk + ' '
        print(command)

        quit()

    print('All chunks are valid, encoding finished successfully')


if __name__ == "__main__":

    # if a user does 'python main.py clear' then clear the celery queue
    if len(sys.argv) > 1 and sys.argv[1] == 'clear':
        print('Clearing celery queue')
        app.control.purge()
        quit()

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Encode a video using SVT-AV1, and mux it with ffmpeg')
    parser.add_argument('input', type=str, help='Input video file')
    parser.add_argument('temp_dir', help='Temp directory', nargs='?', default='temp/', type=str, metavar='temp_dir')
    parser.add_argument('output', type=str, help='Output video file')
    parser.add_argument('--audio', help='Mux audio', action='store_true', default=True)
    parser.add_argument('--celeryless', help='Encode without celery', action='store_true', default=False)
    parser.add_argument('--dry', help='Dry run, dont actually encode', action='store_true', default=False)
    parser.add_argument('--autocrop', help='Automatically crop the video', action='store_true')
    parser.add_argument('--crop_override', help='Override the crop', type=str, default='')
    parser.add_argument('--mux', help='Mux the video and audio together', action='store_true', default=False)
    parser.add_argument('--integrity_check', help='Check for intergrity of encoded files', action='store_true',
                        default=True)
    parser.add_argument('--bitrate', help='Bitrate to use', type=str, default='2000k')
    parser.add_argument('--convexhull', help='Enable convexhull', action='store_true', default=False)
    parser.add_argument('--multiprocess_workers', help='Number of workers to use for multiprocessing', type=int,
                        default=7)

    # auto grain
    parser.add_argument('--autograin', help="Automagicly pick grainsynth value", action='store_true', default=False)

    # grain override
    parser.add_argument('--grainsynth', help="Manually give the grainsynth value, 0 to disable", type=int, default=7,
                        choices=range(0, 63))

    # target vmaf
    parser.add_argument('--vmaf', help='Target vmaf', type=float, default=95)

    args = parser.parse_args()

    input_path = args.input

    # check if input is an absolute path
    if input_path[0] != '/':
        print('Input video is not absolute, please use absolute paths')

    # do convexhull 😍 sometime maybe
    bitraten = args.bitrate

    # usually the local network ip of the machine running the host
    host_adrees = get_lan_ip()
    print(f'Got lan ip: {host_adrees}')

    # if true, the script will not actually encode the chunks, just print the commands
    dry_run = args.dry

    tempfolder = args.temp_dir
    # turn tempfolder into a full path
    tempfolder = os.path.abspath(tempfolder) + '/'
    input_file = tempfolder + 'temp.mkv'

    DontUseCelery = args.celeryless

    if dry_run and not DontUseCelery:
        print('Dryrun can only work locally using multiprocessing mode')
        quit()

    if not DontUseCelery:
        with app.connection() as connection:
            num_workers = app.control.inspect().active_queues()
            print(f'Number of available workers: {len(num_workers)}')
    else:
        print('Not using celery, using multiprocessing instead')

    if not os.path.exists(tempfolder):
        os.mkdir(tempfolder)
    else:
        syscmd(f'rm {tempfolder}*.log')

    # copy input file to temp folder
    if not os.path.exists(input_file):
        os.system(f'cp "{input_path}" "{input_file}"')

    # example: crop=3840:1600:0:280,scale=1920:800:flags=lanczos
    croppy_floppy = args.crop_override

    DoAutoCrop = args.autocrop

    if DoAutoCrop and croppy_floppy == '':
        cropdetect = do_cropdetect(ChunkObject(path=input_file))
        if cropdetect != '':
            croppy_floppy = f'-vf "crop={cropdetect}"'

    sceneCacheFileName = tempfolder + 'sceneCache.json'

    encoded_scenes = []  # list of strings, that are paths to already encoded chunks
    scenes = get_video_scene_list(input_file, sceneCacheFileName)  # list of [first frame index, last frame index]

    config = EncoderConfigObject()
    config.two_pass = True
    config.crop_string = croppy_floppy
    config.bitrate = bitraten
    config.vmaf = args.vmaf
    config.convexhull = args.convexhull
    config.temp_folder = tempfolder
    config.server_ip = host_adrees
    config.remote_path = tempfolder
    config.dry_run = dry_run

    if args.autograin:
        # create temp folder
        tmp_dir = tempfile.mkdtemp()
        config.grainsynth = get_best_avg_grainsynth(input_file=input_file,
                                                    scenes=scenes,
                                                    temp_folder=tmp_dir,
                                                    cache_filename=tempfolder + 'ideal_grain.pt')
        # remove temp folder
        shutil.rmtree(tmp_dir)
    else:
        config.grainsynth = args.grainsynth

    process_chunks(scenes, input_file, config, celeryless_encoding=DontUseCelery,
                   multiprocess_workers=args.multiprocess_workers)

    # if we are doing a dry run the process chunks will spit out the commands, so we quit here
    if dry_run:
        quit()

    if args.integrity_check:
        integrity_check(tempfolder, scenes)
    else:
        print('WARNING: integrity check is disabled, this is not recommended')

    mux_at_the_end = args.mux
    mux_output = args.output
    mux_audio = args.audio

    # default, general audio params
    audio_params = '-c:a libopus -ac 2 -b:v 96k -vbr on'
    if not mux_at_the_end:
        quit()

    if len(mux_output) == 0:
        print('If muxing please provide a output path')
        quit()

    if os.path.exists(mux_output):
        print(f'File {mux_output} already exists')
        quit()

    concat_file_path = 'mhmconcat'

    with open(concat_file_path, 'w') as f:
        for i, frag in enumerate(scenes):
            print(i)
            f.write(f"file '{tempfolder}{i}.ivf'\n")

    # if the audio flag is set then mux the audio
    if mux_audio:
        print('muxing audio innt luv')
        if len(audio_params) == 0:
            audio_params = '-c:a libopus -ac 2 -b:v 96k -vbr on'

        kumannds = [
            f"ffmpeg -v error -f concat -safe 0 -i {concat_file_path} -i {tempfolder}temp.mkv -map 0:v -map 1:a {audio_params} -movflags +faststart -c:v copy temp_{mux_output}",
            f"mkvmerge -o {mux_output} temp_{mux_output}",
            f"rm temp_{mux_output} {concat_file_path}"
        ]

        for command in kumannds:
            print('Running: ' + command)
            os.system(command)
    else:
        print("not muxing audio")
        kumannds = [
            f"ffmpeg -v error -f concat -safe 0 -i {concat_file_path} -c copy -movflags +faststart temp_" + mux_output,
            f"mkvmerge -o {mux_output} temp_{mux_output}",
            f"rm temp_{mux_output} {concat_file_path}"
        ]
        for command in kumannds:
            print('Running: ' + command)
            os.system(command)
        print(f'Removing {concat_file_path}')
        os.system(f'rm {concat_file_path}')
