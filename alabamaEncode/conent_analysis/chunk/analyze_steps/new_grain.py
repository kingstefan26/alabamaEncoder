import os
import subprocess

import numpy as np

from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.timer import Timer
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.scene_detection import scene_detect


class NewGrainSynth(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        grain_synth_result = ctx.get_kv().get("grain_synth", chunk.chunk_path)

        if grain_synth_result is None:
            grain_synth_result = calc_grainsynth_of_scene_fast(
                chunk,
                scale_vf=ctx.scale_string,
                crop_vf=ctx.crop_string,
            )
            grain_synth_result = min(grain_synth_result, 18)

            enc.grain_synth = int(grain_synth_result)
            ctx.get_kv().set("grain_synth", chunk.chunk_path, grain_synth_result)
        else:
            enc.grain_synth = int(grain_synth_result)

        ctx.log(f"{chunk.log_prefix()}computed gs {enc.grain_synth}", category="grain")

        return enc


def measure_output_size(command):
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    total_size = 0

    while process.poll() is None:
        chunk = process.stdout.read(1024 * 1024)
        if chunk:
            total_size += len(chunk)

    # Ensure the process has finished
    process.wait()

    return total_size


def inference(data):
    from itertools import combinations_with_replacement

    n_samples, n_features = data.shape
    combinations = list(combinations_with_replacement(range(n_features), 2))
    X_poly = np.ones((n_samples, len(combinations)))

    for i, index_comb in enumerate(combinations):
        X_poly[:, i] = np.prod(data[:, index_comb], axis=1)

    new_data_poly = X_poly

    new_data_poly_b = np.c_[np.ones((new_data_poly.shape[0], 1)), new_data_poly]
    weights = np.array([34.31016125, 2333.23498342, -4837.40104381, 2474.86714525])
    res = np.dot(new_data_poly_b, weights)
    return int(res[0])


def calc_grainsynth_of_scene_fast(
    chunk: ChunkObject, scale_vf="", crop_vf="", return_source_values=False
) -> int:
    filter_vec = []
    if crop_vf != "" and crop_vf is not None:
        filter_vec.append(f"crop={crop_vf}")

    if scale_vf != "" and scale_vf is not None:
        filter_vec.append(f"scale={scale_vf}:flags=lanczos")

    denoise_weak = "vaguedenoiser"
    denoise_strong = "vaguedenoiser=threshold=6"

    timer = Timer()

    timer.start("scene_gs_approximation")

    common = (
        f"{get_binary('ffmpeg')} -v error "
        f"-y {chunk.get_ss_ffmpeg_command_pair()} -pix_fmt yuv420p10le -c:v huffyuv -an -f nut "
    )
    a = ",".join(filter_vec)
    if a != "":
        a = f" -vf {a}"

    timer.start("ref")
    ref_size = measure_output_size(f"{common} {a} -")
    timer.stop("ref")

    timer.start("strong")
    strong_size = measure_output_size(
        f"{common} -vf {",".join(filter_vec + [denoise_strong])} -"
    )
    timer.stop("strong")

    timer.start("weak")
    weak_size = measure_output_size(
        f"{common} -vf {",".join(filter_vec + [denoise_weak])} -"
    )
    timer.stop("weak")

    normalised_weak = weak_size / ref_size
    normalised_strong = strong_size / ref_size

    final_grain = inference(np.array([[normalised_weak, normalised_strong]]))

    timer.stop("scene_gs_approximation")
    timer.finish(loud=True)
    if return_source_values:
        return {
            "ref_size": ref_size,
            "weak_size": weak_size,
            "strong_size": strong_size,
        }
    else:
        return final_grain


def test():
    test_env = "./experiments/grain_synth/"
    test_env = os.path.abspath(test_env)

    if not os.path.exists(test_env):
        os.makedirs(test_env)

    scene_list = scene_detect(
        input_file="/home/kokoniara/ep3_halo_test.mkv",
        cache_file_path=test_env + "sceneCache.pt",
    )

    for chunk in scene_list.chunks:
        print(
            "calculated gs: "
            + str(
                calc_grainsynth_of_scene_fast(
                    chunk, crop_vf="3840:1920:0:120", scale_vf="1920:-2"
                )
            )
        )
        print("\n\n")


if __name__ == "__main__":
    test()
