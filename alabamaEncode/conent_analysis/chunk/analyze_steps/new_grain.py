import os
import subprocess

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


def calc_grainsynth_of_scene(
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

    print(
        f"denoise stats: size of ref: {ref_size}, size of weak: {weak_size}, size of strong: {strong_size}"
    )

    ratio_ref_strong = ref_size / strong_size
    ratio_ref_weak = ref_size / weak_size
    ratio_strong_weak = strong_size / weak_size
    print(
        f"ratio_ref_strong: {ratio_ref_strong}, ratio_ref_weak: {ratio_ref_weak},"
        f" ratio_strong_weak: {ratio_strong_weak}"
    )

    grain_factor = ref_size * 100.0 / weak_size
    grain_factor = (
        ((ref_size * 100.0 / strong_size * 100.0 / grain_factor) - 105.0) * 8.0 / 10.0
    )
    final_grain = 0

    print(f"Frame grain using old formula (obv wrong): {int(grain_factor / 2)}")

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
                calc_grainsynth_of_scene(
                    chunk,
                    test_env,
                    crop_vf="3840:1920:0:120",
                    scale_vf="1920:-2",
                    # parallel=True,
                )
            )
        )
        print("\n\n")


if __name__ == "__main__":
    test()
