import json
import os
import random

from torf import Torrent
from tqdm import tqdm

from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.path import PathAlabama
from alabamaEncode.utils.execute import syscmd


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

    cc = open(f"{output_folder}temp/chunks.log").read()
    lines = cc.split("\n")
    stats = [json.loads(line) for line in lines if line]

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
