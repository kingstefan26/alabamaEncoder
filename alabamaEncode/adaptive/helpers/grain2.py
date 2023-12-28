"""
big inspiration from:
https://github.com/porcino/Av1ador/blob/4b58a460000acdaee669b61a6e8500c925e3c3bd/Av1ador/Video.cs#L436
"""

import copy
import os
from math import sqrt
from statistics import mean

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.scene.chunk import ChunkObject


def calc_grainsynth_of_scene(
    _chunk: ChunkObject,
    probe_dir: str,
    encoder_max_grain: int = 50,
    scale_vf="",
    crop_vf="",
    threads=1,
) -> int:
    chunk: ChunkObject = copy.deepcopy(_chunk)

    reference_path = probe_dir + "reference.png"
    test1_path = probe_dir + "test1.png"
    test2_path = probe_dir + "test2.png"

    a = f""
    if crop_vf != "" and crop_vf is not None:
        a += f"crop={crop_vf}"

    if scale_vf != "" and scale_vf is not None:
        if a != "":
            a += ","
        a += f"scale={scale_vf}:flags=lanczos"

    b = "nlmeans=s=4:p=5:r=15,format=pix_fmts=yuv420p"
    c = "nlmeans=s=1.8:p=7:r=9,format=pix_fmts=yuv420p"

    if a != "":
        b = f"{a},{b}"
        c = f"{a},{c}"
        a = f" -vf {a}"

    gs = []

    chunk_frame_lenght = chunk.last_frame_index - chunk.first_frame_index
    loop_count = int((5 + sqrt(chunk_frame_lenght / 5)) / 2)  # magic
    comamnds = []
    for i in range(loop_count):
        try:
            curr = chunk.first_frame_index + int((chunk_frame_lenght / loop_count) * i)
            chunk.first_frame_index = curr
            if chunk.first_frame_index > chunk.last_frame_index:
                chunk.first_frame_index = chunk.last_frame_index - 1
            avvs = (
                f"{get_binary('ffmpeg')} -v error -threads {threads} "
                f"-y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1"
            )
            cli = f'{avvs}  {a} -pix_fmt yuv420p "{reference_path}"'
            cli1 = f'{avvs} -vf {b} "{test1_path}"'
            cli2 = f'{avvs} -vf {c} "{test2_path}"'
            comamnds += [cli, cli1, cli2]

            run_cli(cli).verify(files=[reference_path])
            ref_size = os.path.getsize(reference_path)
            os.remove(reference_path)

            run_cli(cli1).verify(files=[test1_path])
            test2_size = os.path.getsize(test1_path)
            os.remove(test1_path)

            run_cli(cli2).verify(files=[test2_path])
            test1_size = os.path.getsize(test2_path)
            os.remove(test2_path)

            grain_factor = ref_size * 100.0 / test1_size
            grain_factor = (
                ((ref_size * 100.0 / test2_size * 100.0 / grain_factor) - 105.0)
                * 8.0
                / 10.0
            )

            # magic empirical values
            grain_factor = max(0.0, min(100.0, grain_factor))
            # print(f"{chunk.log_prefix()}grain factor: {grain_factor}")
            gs.append(grain_factor)
        except RuntimeError:
            pass
    if len(gs) == 0:
        print(comamnds)
        print("loop count:", loop_count)
        print("chunk_frame_lenght:", chunk_frame_lenght)
        raise RuntimeError("No grain factors found")
    final_grain = mean(gs)
    final_grain /= 100.0 / encoder_max_grain
    final_grain = int(final_grain)

    # print(f"{chunk.log_prefix()}grain adjusted for encoder max: {final_grain}")
    return final_grain
