import re

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.scene.chunk import ChunkObject


def get_video_psnr(distorted_path, in_chunk: ChunkObject = None):
    null_ = in_chunk.create_chunk_ffmpeg_pipe_command()
    null_ += f" | {get_binary('ffmpeg')} -hide_banner -i - "

    null_ += f" -i {distorted_path} -filter_complex psnr -f null -"

    result_string = run_cli(null_).get_output()
    try:
        # Regex to get avrage score out of:
        # [Parsed_psnr_0 @ 0x55f6705fa200] PSNR y:49.460782 u:52.207017 v:51.497660 average:50.118351
        # min:48.908778 max:51.443411

        psnr_score = float(re.search(r"average:([\d.]+)", result_string).group(1))
        return psnr_score
    except AttributeError:
        print(f"Failed getting psnr comparing {distorted_path} agains {in_chunk.path}")
        print(null_)
        return 0
