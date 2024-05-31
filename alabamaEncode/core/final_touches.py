import json
import os
import random

from torf import Torrent
from tqdm import tqdm

from alabamaEncode.cli.cli_setup.autopaths import is_title_movie, parse_movie_title
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.path import PathAlabama


def print_stats(
    output_folder: str,
    output: str,
    title: str,
):
    result_file = f"{output_folder}/stat.txt"
    if os.path.exists(result_file):
        os.remove(result_file)

    def ps(s):
        print(s)
        with open(result_file, "a") as stat_file:
            stat_file.write(s + "\n")

    output_file = PathAlabama(output)

    def sizeof_fmt(num, suffix="B"):
        for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Yi{suffix}"


    # Title: <Title> <episode & seson if applicable>
    # IMDB: <id>
    # Runtime: hh:mm:ss
    # Size: 0.00 GB|MB
    #
    # Video (<codec>):
    # <width>x<height> - <8|10|12>-bit <HDR> - 0000 kbps
    #
    # Audio (<codec>):
    # English <channel layout eg 7.1> - 000 kbps
    #
    # Subtitles (<number of subs tracks>x <sub title codec eg SRT>):
    # <All subtitle langs comma separated>
    #
    # Encoder / Settings: <encoder used eg svt-av1-psy>, Preset <speed used eg 4>, <rd mode eg target-quality VMAF 94>, < gs used if applicable eg Grain Synth 5>
    #
    # <if av1 is used this message:
    #     Compatibility: Windows/Android: VLC or MPV - Oculus: SkyboxVR 1.1.0 or later - TVs: Most smart TVs from 2020 or newer>

    size_bytes = os.path.getsize(output_file.get()) * 8

    width, height = Ffmpeg.get_width(output_file),  Ffmpeg.get_height(output_file)

    bitdepth = Ffmpeg.get_bit_depth(output_file)

    hdr = Ffmpeg.is_hdr(output_file)

    vid_bps, audio_bps = Ffmpeg.get_source_bitrates(output_file)

    tracks = Ffmpeg.get_tracks(output_file)

    # running under one vid track assumption
    video_tracks = []
    # running under one audio track assumption
    audio_tracks = []
    sub_tracks = []

    for track in tracks:
        if track["codec_type"] == "subtitle":
            sub_tracks.append(track)
        elif track["codec_type"] == "audio":
            audio_tracks.append(track)
        elif track["codec_type"] == "video":
            video_tracks.append(track)
    lenght = Ffmpeg.get_video_length(output_file, sexagesimal=True)
    vid_codec = video_tracks[0]["codec_name"].upper()
    audio_codec = audio_tracks[0]["codec_name"].upper()
    sub_codec = sub_tracks[0]["codec_name"].upper()

    sub_langs_list = []
    for sub_track in sub_tracks:
        lang = "N/A"
        if "title" in sub_track["tags"]:
            lang = sub_track["tags"]["title"]
        elif "language" in sub_track["tags"]:
            lang = sub_track["tags"]["language"]
        sub_langs_list.append(lang)

    print("\n")

    if is_title_movie(title):
        title, year = parse_movie_title(title)
        ps(f"Title: {title}")
    else:
        ps(f"Title: {title}")

    ps("IMDB: <filled manually>")

    ps(f"Runtime: {lenght}")

    ps(f"Size: {sizeof_fmt(size_bytes)}")
    ps('\n')

    ps(f"Video ({vid_codec}):")
    ps(f"{width}x{height} - {bitdepth}-bit {'HDR' if hdr else 'SDR'} - {vid_bps // 1000} kbps")
    ps('\n')


    ps(f"Audio ({audio_codec}):")
    for audio_track in audio_tracks:
        lang = "N/A"
        if "language" in audio_track["tags"]:
            lang = audio_track["tags"]["language"]
        ps(f"{lang} {audio_track['channel_layout']} - {audio_bps // 1000} kbps")

    ps('\n')

    ps(f"Subtitles ({len(sub_tracks)}x {sub_codec}):")

    ps(", ".join(sub_langs_list))

    ps('\n')

    ps('Encoder / Settings: <FILL MANUALLY>')

    if vid_codec == "AV1":
        ps("Compatibility: Windows/Android: VLC or MPV - Oculus: SkyboxVR 1.1.0 or later - TVs: Most smart TVs from 2020 or newer")

    ps('\n')


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
        jpeg_preview_path = f"{output_folder}/preview_{i}.jpeg"
        run_cli(
            f'{get_binary("ffmpeg")} -y -ss {offset}'
            f' -i "{input_file}" -v:frames 1 -pix_fmt rgb24 "{png_preview_path}"'
        )
        run_cli(
            f'cat "{png_preview_path}" | {get_binary("cjpeg")} -q 95 -tune-psnr -optimize -progressive > '
            f'"{jpeg_preview_path}"')
        run_cli(f'{get_binary("ect")} "{png_preview_path}"')
        run_cli(f'{get_binary("ect")} "{jpeg_preview_path}"')
        # try:
        #     pass
        # except BinaryNotFound:
        #     print("cjpeg or ect not found, skipping jpeg preview/png optimization")


if __name__ == "__main__":
    # register_bin("ect", "/home/kokoniara/.local/opt/ect")
    # generate_previews(
    #     "/home/kokoniara/dev/VideoSplit/test_codes/lessons_in_meth_fast13_slow4/out.mp4",
    #     "/home/kokoniara/dev/VideoSplit/test_codes/lessons_in_meth_fast13_slow4/",
    # )
    tracks = Ffmpeg.get_tracks(PathAlabama("/home/kokoniara/showsEncode/Foundation (2021)/s2/Foundation.2021.S02.1080p.AV1.OPUS.SouAV1R/Foundation.2021.S02E08.1080p.AV1.OPUS.SouAV1R.webm"))
    # pretty print the dictionary
    print(json.dumps(tracks,sort_keys=True, indent=4))



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

    torrent_file_path = os.path.join(output_folder, "torrent.torrent")

    if os.path.exists(torrent_file_path):
        os.remove(torrent_file_path)
    t.write(torrent_file_path)
