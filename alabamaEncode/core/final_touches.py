import os
import random

from torf import Torrent
from tqdm import tqdm

from alabamaEncode.core.util.bin_utils import get_binary, register_bin, BinaryNotFound
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.path import PathAlabama


def print_stats(
    output_folder: str,
    output: str,
    input_file: str,
    grain_synth: int,
    title: str,
    tonemaped: bool,
    croped: bool,
    scaled: bool,
    cut_intro: bool,
    cut_credits: bool,
):
    # sum up all the time_encoding variables

    # remove old stat.txt
    result_file = f"{output_folder}/stat.txt"
    if os.path.exists(result_file):
        os.remove(result_file)

    def print_and_save(s: str):
        print(s)
        with open(result_file, "a") as stat_file:
            stat_file.write(s + "\n")

    total_bitrate = int(Ffmpeg.get_total_bitrate(PathAlabama(output))) / 1000

    print_and_save("\n")

    def sizeof_fmt(num, suffix="B"):
        for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Yi{suffix}"

    print_and_save(f"## {title}")

    lines = []

    lines.append(f"- total bitrate `{total_bitrate} kb/s`")
    lines.append(f"- total size `{sizeof_fmt(os.path.getsize(output)).strip()}`")
    lines.append(
        f"- length `{Ffmpeg.get_video_length(PathAlabama(output), True).split('.')[0]}`"
    )
    size_decrease = round(
        (os.path.getsize(output) - os.path.getsize(input_file))
        / (os.path.getsize(input_file))
        * 100,
        2,
    )
    lines.append(
        f"- sause `{os.path.basename(input_file)}`, size `{sizeof_fmt(os.path.getsize(input_file))}`, size decrease "
        f"from source `{size_decrease}%`"
    )

    if grain_synth == -2:
        grain_synth = "per scene"
    lines.append(f"- grain synth `{grain_synth}`")

    arr = []
    if tonemaped:
        arr.append("tonemaped")
    if croped:
        arr.append("croped")
    if scaled:
        arr.append("scaled")
    if len(arr) > 0:
        lines.append(f"- {' & '.join(arr)}")

    if cut_intro and cut_credits is False:
        lines.append(f"- intro cut")
    elif cut_intro is False and cut_credits:
        lines.append(f"- credits cut")
    elif cut_intro and cut_credits:
        lines.append(f"- intro & credits cut")

    print_and_save("\n".join(lines))

    print_and_save("\n")


def generate_previews(input_file: str, output_folder: str):
    total_length = Ffmpeg.get_video_length(PathAlabama(input_file))  # lenght in seconds

    # one preview every 5 minutes, min 1 max 4
    num_previews = max(1, min(4, int(total_length / 300)))

    offsets = []

    for i in range(num_previews):
        offsets.append(int(random.uniform(0, total_length)))

    is_av1 = Ffmpeg.get_codec(PathAlabama(input_file)) == "av1"

    for i, offset in tqdm(enumerate(offsets), desc="Generating previews", total=num_previews):
        # create additional avif stream copy previews
        if is_av1:
            run_cli(
                f'{get_binary("ffmpeg")} -y -ss {offset} -i "{input_file}" -t 5 '
                f'-c copy "{output_folder}/preview_{i}.avif"'
            )
        png_preview_path = f"{output_folder}/preview_{i}.png"
        run_cli(
            f'{get_binary("ffmpeg")} -y -ss {offset}'
            f' -i "{input_file}" -v:frames 1 -pix_fmt rgb24 "{png_preview_path}"'
        )
        try:
            run_cli(
                f'cat {png_preview_path} | {get_binary("cjpeg")} -q 95 -tune-psnr -optimize -progressive >'
                f' "{png_preview_path.replace(".png", ".jpg")}"'
            )
            run_cli(f'{get_binary("ect")} "{png_preview_path}"')
        except BinaryNotFound:
            print("cjpeg or ect not found, skipping jpeg preview/png optimization")


if __name__ == "__main__":
    register_bin("ect", "/home/kokoniara/.local/opt/ect")
    generate_previews(
        "/home/kokoniara/dev/VideoSplit/test_codes/lessons_in_meth_fast13_slow4/out.mp4",
        "/home/kokoniara/dev/VideoSplit/test_codes/lessons_in_meth_fast13_slow4/",
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
