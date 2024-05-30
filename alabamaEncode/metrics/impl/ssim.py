import os
import re

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.scene.chunk import ChunkObject


def get_video_ssim(
    distorted_path,
    in_chunk: ChunkObject = None,
    print_output=False,
    get_db=False,
    video_filters="",
):
    if not os.path.exists(in_chunk.path) or not os.path.exists(distorted_path):
        raise FileNotFoundError(
            f"File {in_chunk.path} or {distorted_path} does not exist"
        )
    null_ = in_chunk.create_chunk_ffmpeg_pipe_command(video_filters=video_filters)

    null_ += f" | {get_binary('ffmpeg')} -hide_banner -i - -i {distorted_path} -filter_complex ssim -f null -"

    result_string = run_cli(null_).get_output()
    if print_output:
        print(result_string)
    try:
        # Regex to get avrage score out of:
        # [Parsed_ssim_0 @ 0x55f6705fa200] SSIM Y:0.999999 (0.000000 dB) U:0.999999 (0.000000 dB)
        # V:0.999999 (0.000000 dB) All:0.999999 (0.000000)
        match = re.search(r"All:([\d.]+) \(([\d.]+)", result_string)
        ssim_score = float(match.group(1))
        ssim_db = float(match.group(2))

        if get_db is True:
            return ssim_score, ssim_db
        else:
            return ssim_score
    except AttributeError:
        print(f"Failed getting ssim comparing {distorted_path} agains {in_chunk.path}")
        print(null_)
        return 0
