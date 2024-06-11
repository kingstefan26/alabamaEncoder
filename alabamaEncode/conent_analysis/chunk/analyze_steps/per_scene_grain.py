"""
big inspiration from:
https://github.com/porcino/Av1ador/blob/4b58a460000acdaee669b61a6e8500c925e3c3bd/Av1ador/Video.cs#L436
"""

import copy
import os
import subprocess
from math import sqrt
from statistics import mean

from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.timer import Timer
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.scene_detection import scene_detect


class GrainSynth(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        grain_synth_result = ctx.get_kv().get("grain_synth", chunk.chunk_path)

        if grain_synth_result is None:
            grain_synth_result = calc_grainsynth_of_scene(
                chunk,
                scale_vf=ctx.scale_string,
                crop_vf=ctx.crop_string,
            )
            grain_synth_result = min(grain_synth_result, 18)

            enc.grain_synth = int(grain_synth_result)
            ctx.get_kv().set("grain_synth", chunk.chunk_path, grain_synth_result)
        else:
            enc.grain_synth = int(grain_synth_result)

        # if ctx.simple_denoise and grain_synth_result != 0:
        #     grain_synth_result /= 1.5
        ctx.log(f"{chunk.log_prefix()}computed gs {enc.grain_synth}", category="grain")

        return enc


def calc_grainsynth_of_scene(
    _chunk: ChunkObject,
    encoder_max_grain: int = 50,
    scale_vf="",
    crop_vf="",
    print_timing=False,
) -> int:
    chunk: ChunkObject = copy.deepcopy(_chunk)

    filter_vec = []
    if crop_vf != "" and crop_vf is not None:
        filter_vec.append(f"crop={crop_vf}")

    if scale_vf != "" and scale_vf is not None:
        filter_vec.append(f"scale={scale_vf}:flags=lanczos")

    denoise_weak = "nlmeans=s=1.8:p=7:r=9"
    denoise_strong = "nlmeans=s=4:p=5:r=15"

    timer = Timer()

    timer.start("scene_gs_approximation")

    filters_ref = ",".join(filter_vec)
    if filters_ref != "" and "vf" not in filters_ref:
        filters_ref = f" -vf {filters_ref}"
    filters_weak = ",".join(filter_vec + [denoise_weak])
    filters_weak = f" -vf {filters_weak}"
    filters_strong = ",".join(filter_vec + [denoise_strong])
    filters_strong = f" -vf {filters_strong}"

    gs = []

    chunk_frame_lenght = chunk.last_frame_index - chunk.first_frame_index
    loop_count = int((5 + sqrt(chunk_frame_lenght / 5)) / 2)  # magic
    for i in range(loop_count):
        curr = chunk.first_frame_index + int((chunk_frame_lenght / loop_count) * i)
        chunk.first_frame_index = curr

        if chunk.first_frame_index > chunk.last_frame_index:
            chunk.first_frame_index = chunk.last_frame_index - 1

        common = (
            f"{get_binary('ffmpeg')} -v error "
            f"-y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 -pix_fmt yuv420p "
            f" -f image2pipe -c:v png "
        )

        timer.start(f"calc_scene_{i}")

        ref_size = get_size(f"{common} {filters_ref} -")
        if ref_size == 0:
            continue
        weak_size = get_size(f"{common} {filters_weak} -")
        if weak_size == 0:
            continue
        strong_size = get_size(f"{common} {filters_strong} -")
        if strong_size == 0:
            continue

        timer.stop(f"calc_scene_{i}")

        grain_factor = ref_size * 100.0 / weak_size
        grain_factor = (
            ((ref_size * 100.0 / strong_size * 100.0 / grain_factor) - 105.0)
            * 8.0
            / 10.0
        )

        # print(f"Frame grain: {int(grain_factor / (100.0 / encoder_max_grain))}")

        # magic empirical values
        grain_factor = max(0.0, min(100.0, grain_factor))
        gs.append(grain_factor)

    if len(gs) == 0:
        raise RuntimeError("No grain factors found")

    final_grain = mean(gs)
    final_grain /= 100.0 / encoder_max_grain
    final_grain = int(final_grain)

    timer.stop("scene_gs_approximation")
    timer.finish(loud=print_timing)

    return final_grain


def get_size(command):
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    total_size = 0

    while process.poll() is None:
        chunk = process.stdout.read(1024 * 1024)
        if chunk:
            total_size += len(chunk)

    process.wait()

    return total_size


def test():
    test_env = "./experiments/grain_synth/"
    test_env = os.path.abspath(test_env)

    if not os.path.exists(test_env):
        os.makedirs(test_env)

    scene_list = scene_detect(
        input_file="/home/kokoniara/ep3_halo_test.mkv",
        cache_file_path=test_env + "sceneCache.pt",
    )

    grain_values = {}
    for chunk in scene_list.chunks:
        grain_value = calc_grainsynth_of_scene(
            chunk,
            crop_vf="3840:1920:0:120",
            scale_vf="1920:-2",
            # parallel=True,
        )
        print("calculated gs: " + str(grain_value))
        grain_values[str(chunk.chunk_index)] = grain_value

        print("\n\n")

    print(grain_values)


if __name__ == "__main__":
    test()
