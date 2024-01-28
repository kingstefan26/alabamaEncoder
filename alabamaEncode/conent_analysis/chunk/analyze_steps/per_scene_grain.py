"""
big inspiration from:
https://github.com/porcino/Av1ador/blob/4b58a460000acdaee669b61a6e8500c925e3c3bd/Av1ador/Video.cs#L436
"""
import copy
import os
from math import sqrt
from statistics import mean

from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.core.timer import Timer
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.split import get_video_scene_list_skinny


class GrainSynth(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        probe_file_base = ctx.get_probe_file_base(chunk.chunk_path)

        grain_synth_result = ctx.get_kv().get("grain_synth", chunk.chunk_path)

        if grain_synth_result is None:
            grain_synth_result = calc_grainsynth_of_scene(
                chunk,
                probe_file_base,
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


tried_opencl = False
supports_opencl = False


def calc_grainsynth_of_scene(
    _chunk: ChunkObject,
    probe_dir: str,
    encoder_max_grain: int = 50,
    scale_vf="",
    crop_vf="",
    threads=1,
    print_timing=False,
    parallel=False,
    opencl=True,
    alt_blur_version=False,
) -> int:
    chunk: ChunkObject = copy.deepcopy(_chunk)

    # a = f""
    filter_vec = []
    if crop_vf != "" and crop_vf is not None:
        # a += f"crop={crop_vf}"
        filter_vec.append(f"crop={crop_vf}")

    if scale_vf != "" and scale_vf is not None:
        filter_vec.append(f"scale={scale_vf}:flags=lanczos")

    if alt_blur_version:
        raise Exception("NOT FINISHED")
        opencl = False
        denoise_strong = "yaepblur=s=256:r=5"
        denoise_weak = "yaepblur=r=4"
    else:
        denoise_strong = "nlmeans=s=4:p=5:r=15"
        denoise_weak = "nlmeans=s=1.8:p=7:r=9"
    gpu_init = ""

    timer = Timer()

    timer.start("scene_gs_approximation")

    global tried_opencl
    global supports_opencl
    if not tried_opencl and opencl:
        tried_opencl = True
        timer.start("opencl_test")
        test = (
            f"{get_binary('ffmpeg')} -init_hw_device opencl=gpu:1.0 -filter_hw_device gpu -v error"
            ' -i "data:image/png;base64,'
            "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAACXBIWXMAAAAAAAAAAQCEeRdzAAAC4klEQVR4nBWN21LaCABA8w3d"
            "h91Zu1ZlRdlcSAKhgUaIEHIncku1xJAQAkGuIhiEAsW2WkfaCra1t+njzs7+Ze3LeThzZg4wb5Zu2sayU/zQqzzX4m0peCRHFJKwlH"
            "SRExK+fyQc5XBMY2MfB7Wrpg5kKGKfDht8rJEV+/vRFzr5uhI3pXghkbRTiohhKrWTIsmSmPw86rzvVQE+ACVRMOkHWT/Eo3CKwH"
            "QmYopJCUdUKiJhyP2BR6Fbt/F93L3pHQECjgiYX8RgAYNEzC8FUBH/Rflx8IAKGvGITkf2SNxReEdmTS4GJMDtOOhlQF8S8jHgNoe"
            "AIgpzfkjCYAX0aGFcD2MZAlYIRA4iEuEHVIpMh3GFQOUAKmAwj4ICBoo4JMNbGcg3fKraUVqCvPf1veQxELDlhCXuGixlMFSRoQ53"
            "SY0mi8yTrN+rYsjctFoMo8CbZZEucVEjGQU+Tce3o+HizF0OB8sz913/5J3bn1XLkvdRCtzqZ3K8b4v1rM6O7Kt+72WrCXwY1peus+h"
            "XF66zHFQXg+rtcaXLM8zaShZFuzlVRpDd1T/HufSP87PP5y4wsfhpWb4+1i+a+2dFbqCx41Ag51mLr688I0PdTNag6dj6w8LW5rlEj8o"
            "y0Nunp3b+qmNM7b22mugIVHvTJ3lWrVhoahUm+sFlw+nlU5LnkRNAT59xQDsbGxTTo3JxWDpo5ZnWDmFvePe211+Z6n+3i3+XN//"
            "fffzxemYG0QLoO1GTgKPsTGzp28vDt6eaLT2phVBtbSOP+94eO19Gky+j6d1k+m02O5H4A6+3maKBihRp58KL0+hxPniYCNRQOP/"
            "Xatq/fW6b1/XGG6s6P2rddHtNjlU3NhyeAizhsckRthDR43hhF7M2/2Yf/B57uFKXuQundtloXjq15wUtA8H8b38UIyhgsEGTDVW"
            'kHS0e0BiyHgp32NS02fl0Pf96PZ9Zpfeue3fxZlyrz/Tyi2r5J56D+MPmxah1AAAAAElFTkSuQmCC" -'
            "vf format=pix_fmts=yuv420p,hwupload,nlmeans_opencl,hwdownload,format=pix_fmts=yuv420p "
            f"-f null {os.path.devnull}"
        )
        supports_opencl = run_cli(test).success()
        timer.stop("opencl_test")

    if supports_opencl and opencl:
        denoise_strong = (
            "format=pix_fmts=yuv420p,hwupload,nlmeans_opencl=s=4:p=5:r=15"
            ",hwdownload,format=pix_fmts=yuv420p"
        )
        denoise_weak = (
            "format=pix_fmts=yuv420p,hwupload,nlmeans_opencl=s=1.8:p=7:r=9"
            ",hwdownload,format=pix_fmts=yuv420p"
        )
        gpu_init = "-init_hw_device opencl=gpu:1.0 -filter_hw_device gpu"

    a = ",".join(filter_vec)
    b = ",".join(filter_vec + [denoise_strong])
    c = ",".join(filter_vec + [denoise_weak])

    gs = []

    chunk_frame_lenght = chunk.last_frame_index - chunk.first_frame_index
    loop_count = int((5 + sqrt(chunk_frame_lenght / 5)) / 2)  # magic
    comamnds = []
    if not parallel:
        for i in range(loop_count):
            comamnds = calc_gs_factor(
                a,
                b,
                c,
                chunk,
                chunk_frame_lenght,
                comamnds,
                gpu_init,
                gs,
                i,
                loop_count,
                probe_dir,
                threads,
                timer,
            )
    else:
        from multiprocessing import Pool

        with Pool(threads) as p:
            for i in range(loop_count):
                comamnds = calc_gs_factor(
                    a,
                    b,
                    c,
                    chunk,
                    chunk_frame_lenght,
                    comamnds,
                    gpu_init,
                    gs,
                    i,
                    loop_count,
                    probe_dir,
                    threads,
                    timer,
                )
            p.map(run_cli, comamnds)
    if len(gs) == 0:
        print(comamnds)
        print("loop count:", loop_count)
        print("chunk_frame_lenght:", chunk_frame_lenght)
        raise RuntimeError("No grain factors found")
    final_grain = mean(gs)
    final_grain /= 100.0 / encoder_max_grain
    final_grain = int(final_grain)

    timer.stop("scene_gs_approximation")
    if print_timing:
        timer.finish(loud=True)

    # print(f"{chunk.log_prefix()}grain adjusted for encoder max: {final_grain}")
    return final_grain


def calc_gs_factor(
    a,
    b,
    c,
    chunk,
    chunk_frame_lenght,
    comamnds,
    gpu_init,
    gs,
    i,
    loop_count,
    probe_dir,
    threads,
    timer,
):
    try:
        curr = chunk.first_frame_index + int((chunk_frame_lenght / loop_count) * i)
        chunk.first_frame_index = curr
        if chunk.first_frame_index > chunk.last_frame_index:
            chunk.first_frame_index = chunk.last_frame_index - 1
        avvs = (
            f"{get_binary('ffmpeg')} -v error -threads {threads} {gpu_init} "
            f"-y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 -pix_fmt yuv420p"
        )

        reference_path = probe_dir + f"{i}reference.png"
        test1_path = probe_dir + f"{i}test1.png"
        test2_path = probe_dir + f"{i}test2.png"

        if a != "":
            a = f" -vf {a}"

        cli = f'{avvs} {a} "{reference_path}"'
        cli1 = f'{avvs} -vf {b} "{test1_path}"'
        cli2 = f'{avvs} -vf {c} "{test2_path}"'
        comamnds += [cli, cli1, cli2]

        timer.start(f"calc_scene_{i}")

        run_cli(cli).verify(files=[reference_path])
        ref_size = os.path.getsize(reference_path)
        os.remove(reference_path)

        run_cli(cli1).verify(files=[test1_path])
        test2_size = os.path.getsize(test1_path)
        os.remove(test1_path)

        run_cli(cli2).verify(files=[test2_path])
        test1_size = os.path.getsize(test2_path)
        os.remove(test2_path)

        timer.stop(f"calc_scene_{i}")

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
    return comamnds


def test():
    test_env = "./experiments/grain_synth/"
    test_env = os.path.abspath(test_env)

    if not os.path.exists(test_env):
        os.makedirs(test_env)

    scene_list = get_video_scene_list_skinny(
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
                    print_timing=True,
                    # parallel=True,
                )
            )
        )
        print("\n\n")


def test_altblur():
    test_env = "./experiments/grain_synth/"
    test_env = os.path.abspath(test_env)

    if not os.path.exists(test_env):
        os.makedirs(test_env)

    scene_list = get_video_scene_list_skinny(
        input_file="/home/kokoniara/ep3_halo_test.mkv",
        cache_file_path=test_env + "sceneCache.pt",
    )

    for chunk in scene_list.chunks:
        print(
            "calculated gs altblur: "
            + str(
                calc_grainsynth_of_scene(
                    chunk,
                    test_env,
                    crop_vf="3840:1920:0:120",
                    scale_vf="1920:-2",
                    print_timing=True,
                    opencl=False,
                    alt_blur_version=True,
                )
            )
        )

        print("\n")

        print(
            "calculated gs: "
            + str(
                calc_grainsynth_of_scene(
                    chunk,
                    test_env,
                    crop_vf="3840:1920:0:120",
                    scale_vf="1920:-2",
                    print_timing=True,
                    opencl=False,
                )
            )
        )
        print("\n\n")


if __name__ == "__main__":
    # test()
    test_altblur()
