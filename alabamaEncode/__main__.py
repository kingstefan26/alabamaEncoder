#!/usr/bin/python
import argparse
import asyncio
import atexit
import glob
import json
import os
import random
import sys
import time
from asyncio import Future
from concurrent.futures.thread import ThreadPoolExecutor

from torf import Torrent
from tqdm import tqdm

from alabamaEncode.adaptive.analyser import do_adaptive_analasys
from alabamaEncode.adaptive.executor import AdaptiveCommand
from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.encoders.encoderMisc import EncodersEnum
from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.parallelEncoding.CeleryApp import app, run_command_on_celery
from alabamaEncode.parallelEncoding.CeleryAutoscaler import Load
from alabamaEncode.parallelEncoding.Command import run_command
from alabamaEncode.path import PathAlabama
from alabamaEncode.sceneSplit.VideoConcatenator import VideoConcatenator
from alabamaEncode.sceneSplit.chunk import ChunkObject, ChunkSequence
from alabamaEncode.sceneSplit.split import get_video_scene_list_skinny
from alabamaEncode.utils.binary import doesBinaryExist
from alabamaEncode.utils.execute import syscmd
from alabamaEncode.utils.ffmpegUtil import (
    do_cropdetect,
)

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
    chunk_list: ChunkSequence,
    encdr_config: AlabamaContext,
    chunk_order="sequential",
    use_celery=False,
):
    command_objects = []

    for chunk in chunk_list.chunks:
        if not os.path.exists(chunk.chunk_path):
            obj = AdaptiveCommand()
            obj.setup(chunk, encdr_config)

            command_objects.append(obj)

    # order chunks based on order
    if chunk_order == "random":
        random.shuffle(command_objects)
    elif chunk_order == "length_asc":
        command_objects.sort(key=lambda x: x.job.chunk.length)
    elif chunk_order == "length_desc":
        command_objects.sort(key=lambda x: x.job.chunk.length, reverse=True)
    elif chunk_order == "sequential":
        pass
    elif chunk_order == "sequential_reverse":
        command_objects.reverse()
    else:
        raise ValueError(f"Invalid chunk order: {chunk_order}")

    if len(command_objects) < 10:
        encdr_config.threads = os.cpu_count()

    print(f"Starting encoding of {len(command_objects)} scenes")

    await execute_commands(
        use_celery, command_objects, encdr_config.multiprocess_workers
    )


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


def print_stats(
    output_folder: str,
    output: str,
    config_bitrate: int,
    input_file: str,
    grain_synth: int,
    title: str,
    tonemaped: bool,
    croped: bool,
    scaled: bool,
    cut_intro: bool,
    cut_credits: bool,
):
    # Load all ./temp/stats/*.json object
    stats = []
    for file in glob.glob(f"{output_folder}temp/stats/*.json"):
        with open(file) as f:
            stats.append(json.load(f))

    # sum up all the time_encoding variables
    time_encoding = 0
    for stat in stats:
        time_encoding += stat["time_encoding"]

    # remove old stat.txt
    if os.path.exists(f"{output_folder}stat.txt"):
        os.remove(f"{output_folder}stat.txt")

    def print_and_save(s: str):
        print(s)
        with open(f"{output_folder}stat.txt", "a") as stat_file:
            stat_file.write(s + "\n")

    print_and_save(f"Total encoding time across chunks: {time_encoding} seconds\n\n")

    # get the worst/best/med target_miss_proc
    target_miss_proc = []
    for stat in stats:
        # turn the string into a float then round to two places
        target_miss_proc.append(round(float(stat["target_miss_proc"]), 2))
    target_miss_proc.sort()
    print_and_save("Target miss from encode per chunk encode bitrate:")
    print_and_save(
        f"Average target_miss_proc: {round(sum(target_miss_proc) / len(target_miss_proc), 2)}"
    )
    print_and_save(f"Worst target_miss_proc: {target_miss_proc[-1]}")
    print_and_save(f"Best target_miss_proc: {target_miss_proc[0]}")
    print_and_save(
        f"Median target_miss_proc: {target_miss_proc[int(len(target_miss_proc) / 2)]}"
    )

    print_and_save("\n\n")

    total_bitrate = int(Ffmpeg.get_total_bitrate(PathAlabama(output))) / 1000
    print_and_save(
        f"Total bitrate: {total_bitrate} kb/s, config bitrate: {config_bitrate} kb/s"
    )
    # vid_bitrate, _ = get_source_bitrates(output)
    bitrate_miss = round((total_bitrate - config_bitrate) / config_bitrate * 100, 2)
    print_and_save(f"Bitrate miss from config bitrate: {bitrate_miss}%")

    print_and_save("\n\n")

    def sizeof_fmt(num, suffix="B"):
        for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Yi{suffix}"

    print("Encode finished message \n\n")

    print_and_save(f"## {title}")

    print_and_save(f"- total bitrate `{total_bitrate} kb/s`")
    print_and_save(f"- total size `{sizeof_fmt(os.path.getsize(output)).strip()}`")
    print_and_save(
        f"- length `{Ffmpeg.get_video_length(PathAlabama(output), True).split('.')[0]}`"
    )
    size_decrease = round(
        (os.path.getsize(output) - os.path.getsize(input_file))
        / (os.path.getsize(input_file))
        * 100,
        2,
    )
    print_and_save(
        f"- sause `{os.path.basename(input_file)}`, size `{sizeof_fmt(os.path.getsize(input_file))}`, size decrease from source `{size_decrease}%`"
    )
    print_and_save(f"- grain synth `{grain_synth}`")

    string = ""

    if tonemaped:
        string += "tonemaped "
    if croped:
        string += " & croped "
    if scaled:
        string += " & scaled"

    print_and_save(f"- {string}")

    if cut_intro and cut_credits == False:
        print_and_save(f"- intro cut")
    elif cut_intro == False and cut_credits:
        print_and_save(f"- credits cut")
    elif cut_intro and cut_credits:
        print_and_save(f"- intro & credits cut")

    print_and_save("\n")
    print_and_save(
        f"https://autocompressor.net/av1?v=https://badidea.kokoniara.software/{os.path.basename(output)}&i= poster_url &w={Ffmpeg.get_width(PathAlabama(output))}&h={Ffmpeg.get_height(PathAlabama(output))}"
    )
    print_and_save("\n")
    print_and_save("ALABAMAENCODES © 2024")

    print("\n\n Finished!")


def generate_previews(
    input_file: str, output_folder: str, num_previews: int, preview_length: int
):
    # get total video length
    # total_length =  get_video_lenght(input_file)
    total_length = Ffmpeg.get_video_length(PathAlabama(input_file))

    # create x number of offsets that are evenly spaced and fit in the video
    offsets = []
    # for i in range(num_previews):
    #     offsets.append(int(i * total_length / num_previews))

    # pick x randomly and evenly offseted offsets
    for i in range(num_previews):
        offsets.append(int(random.uniform(0, total_length)))

    for i, offset in tqdm(enumerate(offsets), desc="Generating previews"):
        syscmd(
            f'ffmpeg -y -ss {offset} -i "{input_file}" -t {preview_length} -c copy "{output_folder}preview_{i}.avif"'
        )


def create_torrent_file(video: str, encoder_name: str, output_folder: str):
    trackers = [
        "udp://tracker.opentrackr.org:1337/announce",
        "https://tracker2.ctix.cn:443/announce",
        "https://tracker1.520.jp:443/announce",
        "udp://opentracker.i2p.rocks:6969/announce",
        "udp://tracker.openbittorrent.com:6969/announce",
        "http://tracker.openbittorrent.com:80/announce",
        "udp://open.demonii.com:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.moeking.me:6969/announce",
        "udp://explodie.org:6969/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "http://tracker.openbittorrent.com:80/announce",
        "udp://opentracker.i2p.rocks:6969/announce",
        "udp://tracker.internetwarriors.net:1337/announce",
        "udp://tracker.leechers-paradise.org:6969/announce",
        "udp://coppersurfer.tk:6969/announce",
        "udp://tracker.zer0day.to:1337/announce",
    ]

    print("Creating torrent file")

    t = Torrent(path=video, trackers=trackers)
    t.comment = f"Encoded by {encoder_name}"

    t.private = False

    t.generate()

    if os.path.exists(os.path.join(output_folder, "torrent.torrent")):
        os.remove(os.path.join(output_folder, "torrent.torrent"))
    t.write(os.path.join(output_folder, "torrent.torrent"))


def worker():
    print("Starting celery worker")

    concurrency = 2

    # check if os.environ['CELERY_CONCURRENCY'] is set and set it as the concurrency
    if "CELERY_CONCURRENCY" in os.environ:
        concurrency = os.environ["CELERY_CONCURRENCY"]

    # get the second argument that is the concurrency and set it as the concurrency
    if len(sys.argv) > 2:
        concurrency = sys.argv[2]

    app.worker_main(
        argv=[
            "worker",
            "--loglevel=info",
            f"--concurrency={concurrency}",
            "--without-gossip",
        ]
    )
    quit()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Encode a video using SVT-AV1, and mux it with ffmpeg"
    )
    parser.add_argument("input", type=str, help="Input video file")
    parser.add_argument("output", type=str, help="Output video file")

    parser.add_argument("--audio", help="Mux audio", action="store_true", default=True)

    parser.add_argument(
        "--audio_params",
        help="Audio params",
        type=str,
        default="-c:a libopus -ac 2 -b:v 96k -vbr on -lfe_mix_level 0.5 -mapping_family 1",
    )

    parser.add_argument(
        "--celery",
        help="Encode on a celery cluster, that is at localhost",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--autocrop", help="Automatically crop the video", action="store_true"
    )

    parser.add_argument(
        "--video_filters",
        type=str,
        default="",
        help="Override the crop, put your vf ffmpeg there, example "
        "scale=-2:1080:flags=lanczos,zscale=t=linear..."
        " make sure ffmpeg on all workers has support for the filters you use",
    )

    parser.add_argument(
        "--bitrate",
        help="Bitrate to use, `auto` for auto bitrate selection",
        type=str,
        default="2000",
    )

    parser.add_argument(
        "--overshoot",
        help="How much proc the bitrate_adjust is allowed to overshoot",
        type=int,
        default=200,
    )

    parser.add_argument(
        "--undershoot",
        help="How much proc the bitrate_adjust is allowed to undershoot",
        type=int,
        default=90,
    )

    parser.add_argument(
        "--bitrate_adjust",
        help="Enable automatic bitrate optimisation per chunk",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    parser.add_argument(
        "--multiprocess_workers",
        help="Number of workers to use for multiprocessing, if -1 the program will auto scale",
        type=int,
        default=-1,
    )

    parser.add_argument(
        "--ssim-db-target",
        type=float,
        default=20,
        help="What ssim dB to target when using auto bitrate,"
        " not recommended to set manually, otherwise 21.2 is a good starting"
        " point",
    )

    parser.add_argument(
        "--crf",
        help="What crf to use",
        type=int,
        default=-1,
        choices=range(0, 63),
    )

    parser.add_argument(
        "--encoder",
        help="What encoder to use",
        type=str,
        default="svt_av1",
        choices=["svt_av1", "x265", "aomenc", "x264"],
    )

    parser.add_argument(
        "--grain",
        help="Manually give the grainsynth value, 0 to disable, -1 for auto",
        type=int,
        default=-1,
        choices=range(-1, 63),
    )

    parser.add_argument(
        "--autoparam",
        help="Automagicly chose params",
        action="store_true",
        default=True,
    )

    parser.add_argument(
        "--vmaf_target",
        help="What vmaf to target when using bitrate auto",
        default=96,
        type=int,
    )

    parser.add_argument(
        "--max_scene_length",
        help="If a scene is longer then this, it will recursively cut in the"
        " middle it to get until each chunk is within the max",
        type=int,
        default=10,
        metavar="max_scene_length",
    )

    parser.add_argument(
        "--auto_crf",
        help="Alternative to auto bitrate tuning, that uses crf",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--chunk_order",
        help="Encode chunks in a specific order",
        type=str,
        default="sequential",
        choices=[
            "random",
            "sequential",
            "length_desc",
            "length_asc",
            "sequential_reverse",
        ],
    )

    parser.add_argument(
        "--start_offset",
        help="Offset from the beginning of the video (in seconds), useful for cutting intros etc",
        default=-1,
        type=int,
    )

    parser.add_argument(
        "--end_offset",
        help="Offset from the end of the video (in seconds), useful for cutting end credits outtros etc",
        default=-1,
        type=int,
    )

    parser.add_argument(
        "--bitrate_adjust_mode",
        help="do a complexity analysis on each chunk individually and adjust "
        "bitrate based on that, can overshoot/undershoot a lot, "
        "otherwise do complexity analysis on all chunks ahead of time"
        " and budget it to hit target by normalizing the bitrate",
        type=str,
        default="chunk",
        choices=["chunk", "global"],
    )

    parser.add_argument(
        "--log_level",
        help="Set the log level",
        type=str,
        default="QUIET",
        choices=["NORMAL", "QUIET"],
    )

    parser.add_argument("--status_update_token", type=str)
    parser.add_argument(
        "--status_update_domain", type=str, default="encodestatus.kokoniara.software"
    )

    parser.add_argument(
        "--generate_previews",
        help="Generate previews for encoded file",
        action="store_true",
        default=True,
    )

    parser.add_argument(
        "--override_bad_wrong_cache_path",
        help="Override the check for input file path matching in scene cache loading",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--hdr",
        help="Encode in HDR`, if off and input is HDR, it will be tonemapped to SDR",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--crop_string",
        help="Crop string to use, eg `1920:1080:0:0`, `3840:1600:0:280`. Obtained using the `cropdetect` ffmpeg filter",
        type=str,
        default="",
    )

    parser.add_argument(
        "--scale_string",
        help="Scale string to use, eg. `1920:1080`, `1280:-2`, `1920:1080:force_original_aspect_ratio=decrease`",
        type=str,
        default="",
    )

    parser.add_argument(
        "--dry_run",
        help="Do not encode, just print what would be done",
        action="store_true",
        default=False,
    )

    parser.add_argument("--title", help="Title of the video", type=str, default="")

    parser.add_argument(
        "--encoder_flag_override",
        type=str,
        default="",
        help="Override the encoder flags with this string," " except paths",
    )

    parser.add_argument(
        "--encoder_speed_override",
        type=int,
        choices=range(0, 8),
        default=4,
        help="Override the encoder speed parameter",
    )

    parser.add_argument(
        "--flag1",
        action="store_true",
        help="find what crf matches config.bitrate, encode at that crf and redo if the crf bitrate is higher then set",
    )

    parser.add_argument(
        "--flag2", action="store_true", help="Find bitrate automaticly for flag 1"
    )

    parser.add_argument(
        "--flag3",
        action="store_true",
        help="Find best bitrate using the top 5% of most complex chunks",
    )

    return parser.parse_args()


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

    encoder_name = "SouAV1R"

    args = parse_args()
    input_path = os.path.abspath(args.input)

    # check if input is an absolute path
    if not input_path.startswith("/"):
        print("Input video is not absolute, please use absolute paths")

    # make --video_filters mutually exclusive with --hdr --crop_string --scale_string
    if args.video_filters != "" and (
        args.hdr or args.video_filters != "" or args.scale_string != ""
    ):
        print(
            "--video_filters is mutually exclusive with --hdr --crop_string --scale_string"
        )
        quit()

    # get outputs folder
    output_folder = os.path.dirname(os.path.abspath(args.output)) + "/"

    # turn tempfolder into a full path
    tempfolder = output_folder + "temp/"

    if not os.path.exists(tempfolder):
        os.makedirs(tempfolder)

    global runtime_file
    runtime_file = tempfolder + "runtime.txt"

    input_file = tempfolder + "temp.mkv"

    host_address = get_lan_ip()
    if args.celery:
        print(f"Got lan ip: {host_address}")
        num_workers = app.control.inspect().active_queues()
        if num_workers is None:
            print("No workers detected, please start some")
            quit()
        print(f"Number of available workers: {len(num_workers)}")
    else:
        print("Using multiprocessing instead of celery")

    if not os.path.exists(tempfolder):
        os.mkdir(tempfolder)

    # copy input file to temp folder
    if not os.path.exists(input_file):
        os.system(f'ln -s "{input_path}" "{input_file}"')

    clean_rate_probes(tempfolder)

    if args.encoder == "x265" and args.auto_crf == False:
        print("x265 only supports auto crf, set `--auto_crf true`")
        quit()

    config = AlabamaContext(temp_folder=tempfolder, passes=3, speed=4)

    find_best_bitrate, find_best_grainsynth = setup_config(args, config, input_file)

    chunks_sequence: ChunkSequence = get_video_scene_list_skinny(
        input_file=input_file,
        cache_file_path=tempfolder + "sceneCache.pt",
        max_scene_length=args.max_scene_length,
        start_offset=args.start_offset,
        end_offset=args.end_offset,
        override_bad_wrong_cache_path=args.override_bad_wrong_cache_path,
    )

    chunks_sequence.setup_paths(
        tempfolder, config.get_encoder().get_chunk_file_extension()
    )

    if not os.path.exists(args.output):
        config, chunks_sequence = do_adaptive_analasys(
            chunks_sequence,
            config,
            find_best_grainsynth=find_best_grainsynth,
            find_best_bitrate=find_best_bitrate,
            do_crf=True if args.crf != -1 or args.flag2 else False,
        )

        if config.grain_synth == 0 and config.bitrate < 2000:
            print(
                "Film grain less then 0 and bitrate is low, overriding to 2 film grain"
            )
            config.film_grain = 2

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
                        chunk_order=args.chunk_order,
                        use_celery=args.celery,
                    )
                )
            except KeyboardInterrupt:
                print("Keyboard interrupt, stopping")
                quit()
            finally:
                loop.stop()

        try:
            concat = VideoConcatenator(
                output=args.output,
                file_with_audio=input_file,
                audio_param_override=args.audio_params,
                start_offset=args.start_offset,
                end_offset=args.end_offset,
                title=args.title,
                encoder_name=encoder_name,
            )
            concat.find_files_in_dir(
                folder_path=tempfolder,
                extension=config.get_encoder().get_chunk_file_extension(),
            )
            concat.concat_videos()
        except Exception as e:
            print("Concat at the end failed 😷")
            raise e
    else:
        print("Output file exists 🤑, printing stats")

    print_stats(
        output_folder=output_folder,
        output=args.output,
        config_bitrate=config.bitrate,
        input_file=args.input,
        grain_synth=-1,
        title=args.title,
        cut_intro=True if args.start_offset > 0 else False,
        cut_credits=True if args.end_offset > 0 else False,
        croped=True if args.crop_string != "" else False,
        scaled=True if args.scale_string != "" else False,
        tonemaped=True
        if not args.hdr and Ffmpeg.is_hdr(PathAlabama(input_file))
        else False,
    )
    if args.generate_previews:
        print("Generating previews")
        generate_previews(
            input_file=args.output,
            output_folder=output_folder,
            num_previews=4,
            preview_length=5,
        )
        create_torrent_file(
            video=args.output,
            encoder_name=encoder_name,
            output_folder=output_folder,
        )
    clean_rate_probes(tempfolder)
    quit()


def setup_config(args, config: AlabamaContext, input_file: str):
    config.log_level = 0 if args.log_level == "QUIET" else 1
    config.dry_run = args.dry_run
    config.ssim_db_target = args.ssim_db_target
    config.vmaf = args.vmaf_target
    config.encoder = EncodersEnum.from_str(args.encoder)
    config.vbr_perchunk_optimisation = args.bitrate_adjust
    config.use_celery = args.celery
    config.flag1 = args.flag1
    config.flag2 = args.flag2
    config.flag3 = args.flag3
    config.override_flags = args.encoder_flag_override
    config.speed = args.encoder_speed_override
    config.multiprocess_workers = args.multiprocess_workers
    config.bitrate_adjust_mode = args.bitrate_adjust_mode
    config.bitrate_undershoot = args.undershoot / 100
    config.bitrate_overshoot = args.overshoot / 100
    config.crf_bitrate_mode = args.auto_crf

    if args.crf != -1:
        print("Using crf mode")
        config.crf = args.crf
    if config.flag1 and config.bitrate == -1:
        print("Flag1 requires bitrate to be set --bitrate 2M")
        quit()
    if (
        "auto" in args.bitrate
        or "-1" in args.bitrate
        and config.flag1
        and not config.flag2
    ):
        print("Flag1 and auto bitrate are mutually exclusive")
        quit()
    find_best_bitrate = False
    if "auto" in args.bitrate or "-1" in args.bitrate:
        find_best_bitrate = True
    else:
        if "M" in args.bitrate or "m" in args.bitrate:
            config.bitrate = args.bitrate.replace("M", "")
            config.bitrate = int(config.bitrate) * 1000
        else:
            config.bitrate = args.bitrate.replace("k", "")
            config.bitrate = args.bitrate.replace("K", "")

            try:
                config.bitrate = int(args.bitrate)
            except ValueError:
                raise ValueError("Failed to parse bitrate")
    find_best_grainsynth = True if args.grain == -1 else False
    if find_best_grainsynth and not doesBinaryExist("butteraugli"):
        print("Autograin requires butteraugli in path, please install it")
        quit()
    config.grain_synth = args.grain
    # eg crop=3840:1600:0:280,scale=1920:-2:flags=lanczos
    config.video_filters = args.video_filters
    if config.video_filters == "":
        if args.autocrop:
            output = do_cropdetect(ChunkObject(path=input_file))
            output.replace("crop=", "")
            if output != "":
                args.video_filters = output

        final = ""

        if args.crop_string != "":
            final += f"crop={args.crop_string}"

        if args.scale_string != "":
            if final != "" and final[-1] != ",":
                final += ","
            final += f"scale={args.scale_string}:flags=lanczos"
        # tonemap_string = 'zscale=t=linear:npl=(>100),format=gbrpf32le,tonemap=tonemap=reinhard:desat=0,zscale=p=bt709:t=bt709:m=bt709:r=tv:d=error_diffusion,format=yuv420p10le'
        tonemap_string = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv:d=error_diffusion"

        if not args.hdr and Ffmpeg.is_hdr(PathAlabama(input_file)):
            if final != "" and final[-1] != ",":
                final += ","
            final += tonemap_string

        config.video_filters = final
    return find_best_bitrate, find_best_grainsynth


if __name__ == "__main__":
    main()
