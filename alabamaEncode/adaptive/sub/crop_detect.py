import re

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject


def do_cropdetect(path: str = None):
    alabama = PathAlabama(path)
    alabama.check_video()
    fps = Ffmpeg.get_video_frame_rate(alabama)
    length = Ffmpeg.get_video_length(alabama) * fps

    #  create a 10-frame long chunk at 20% 40% 60% 80% of the length
    probe_chunks = []
    for i in range(0, 100, 20):
        first_frame_index = int(length * (i / 100))
        probe_chunks.append(
            ChunkObject(
                path=path,
                last_frame_index=first_frame_index + 10,
                first_frame_index=first_frame_index,
                framerate=fps,
            )
        )

    # function that takes a chunk and output its first cropdetect
    def get_crop(chunk) -> str:
        try:
            return re.search(
                r"-?\d+:-?\d+:-?\d+:-?\d+",
                run_cli(
                    f"{get_binary('ffmpeg')} {chunk.get_ss_ffmpeg_command_pair()} -vframes 10 -vf cropdetect -f null -"
                ).get_output(),
            ).group(0)
        except AttributeError:
            return ""

    # get the crops
    crops = [get_crop(chunk) for chunk in probe_chunks]

    # out of the 5 crops, get the most common crop
    most_common_crop = max(set(crops), key=crops.count)

    return most_common_crop
