import os
import random
import struct

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.scene.chunk import ChunkObject

# big shoutout to @master_of_zen for this

fields = [
    "frame",
    "weight",
    "intra_error",
    "frame_avg_wavelet_energy",
    "coded_error",
    "sr_coded_error",
    "tr_coded_error",
    "pcnt_inter",
    "pcnt_motion",
    "pcnt_second_ref",
    "pcnt_third_ref",
    "pcnt_neutral",
    "intra_skip_pct",
    "inactive_zone_rows",
    "inactive_zone_cols",
    "MVr",
    "mvr_abs",
    "MVc",
    "mvc_abs",
    "MVrv",
    "MVcv",
    "mv_in_out_count",
    "new_mv_count",
    "duration",
    "count",
    "raw_error_stdev",
]


def aom_extract_firstpass_data(chunk: ChunkObject, vf=""):
    pass_file_path = f"/tmp/{random.randint(0, 100000)}.pass"

    run_cli(
        f"{chunk.create_chunk_ffmpeg_pipe_command(video_filters=vf)} | {get_binary('aomenc')} - "
        f"--ivf --fpf={pass_file_path} --threads=8 --passes=2 --pass=1 --auto-alt-ref=1 --lag-in-frames=25 "
        f"-o {os.devnull}"
    ).verify()

    dict_list = []

    with open(pass_file_path, "rb") as file:
        frame_buf = file.read(208)
        while len(frame_buf) > 0 and len(frame_buf) % 208 == 0:
            stats = struct.unpack("d" * 26, frame_buf)
            p = dict(zip(fields, stats))
            dict_list.append(p)
            frame_buf = file.read(208)

    os.remove(pass_file_path)

    # print(json.dumps(dict_list, indent=4))
    return dict_list
