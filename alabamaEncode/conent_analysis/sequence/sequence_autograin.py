import copy
import os
import random
import time
from multiprocessing.pool import ThreadPool
from statistics import mean
from typing import List

from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.kv import AlabamaKv
from alabamaEncode.encoder.impl.SvtAvif import AvifEncoderSvtenc
from alabamaEncode.metrics.image import ImageMetrics
from alabamaEncode.scene.sequence import ChunkSequence


def setup_autograin(ctx: AlabamaContext, sequence: ChunkSequence):
    if (
        ctx.prototype_encoder.grain_synth == -1
        and ctx.prototype_encoder.supports_grain_synth()
    ):
        ctx.prototype_encoder.grain_synth = get_best_avg_grainsynth(
            input_file=sequence.input_file,
            scenes=sequence,
            temp_folder=ctx.temp_folder,
            video_filters=ctx.prototype_encoder.video_filters,
            kv=ctx.get_kv(),
            crf=ctx.prototype_encoder.crf,
        )

    return ctx


def find_lowest_x(x_list: List[float], y_list: List[float]) -> float:
    # Check that x_list and y_list are the same length
    if len(x_list) != len(y_list):
        raise ValueError("x_list and y_list must have the same length")

    # Find the minimum y-value and its index
    min_y, min_y_idx = min((y, idx) for idx, y in enumerate(y_list))

    # If the minimum y-value is at the beginning or end of the list, return the corresponding x-value
    if min_y_idx == 0:
        return x_list[0]
    elif min_y_idx == len(y_list) - 1:
        return x_list[-1]

    # Otherwise, use linear interpolation to find the x-value that corresponds to the minimum y-value
    x0 = x_list[min_y_idx - 1]
    x1 = x_list[min_y_idx]
    y0 = y_list[min_y_idx - 1]
    y1 = y_list[min_y_idx]
    slope = (y1 - y0) / (x1 - x0)
    x_min = (min_y - y0) / slope + x0

    return x_min


def get_ideal_grain_butteraugli(encoded_scene_path, chunk, crf, bitrate, vf) -> int:
    start = time.time()

    if "vf" not in vf and vf != "":
        vf = f"-vf {vf}"

    avif_enc = AvifEncoderSvtenc()

    if bitrate != -1:
        avif_enc.bitrate = bitrate
    else:
        avif_enc.crf = crf

    # Create a reference png
    ref_png = encoded_scene_path + ".png"
    if not os.path.exists(ref_png):
        cmd = (
            f'{get_binary("ffmpeg")} -hide_banner -y {chunk.get_ss_ffmpeg_command_pair()} '
            f'{vf} -frames:v 1 "{ref_png}"'
        )

        out = run_cli(cmd)
        if not os.path.exists(ref_png):
            print(cmd)
            raise Exception(f"Could not create reference png: {out}")

    avif_enc.in_path = ref_png

    runs = []

    grain_probes = [0, 1, 4, 6, 11, 16, 21, 26]
    for grain in grain_probes:
        avif_enc.grain_synth = grain
        avif_enc.output_path = encoded_scene_path + ".grain" + str(grain) + ".avif"
        avif_enc.run()

        if not os.path.exists(avif_enc.output_path):
            raise Exception("Encoding of avif Failed")

        decoded_test_png_path = avif_enc.output_path + ".png"

        # turn the avif into a png
        run_cli(
            f'{get_binary("ffmpeg")} -y -i "{avif_enc.output_path}" "{decoded_test_png_path}"'
        )

        if not os.path.exists(decoded_test_png_path):
            raise Exception("Could not create decoded png")

        rd = {
            "grain": grain,
            "butter": ImageMetrics.butteraugli_score(ref_png, decoded_test_png_path),
        }

        os.remove(decoded_test_png_path)
        os.remove(avif_enc.output_path)

        print(f"{chunk.log_prefix()} grain {rd['grain']} -> {rd['butter']} butteraugli")
        runs.append(rd)

    os.remove(ref_png)

    # find the film-grain value that corresponds to the lowest butteraugli score
    ideal_grain = find_lowest_x(
        [point["grain"] for point in runs], [point["butter"] for point in runs]
    )

    print(f"ideal grain is {ideal_grain}, in {int(time.time() - start)} seconds")
    return int(ideal_grain)


def wrapper(obj):
    return get_ideal_grain_butteraugli(**obj)


def get_best_avg_grainsynth(
    input_file: str,
    scenes: ChunkSequence,
    temp_folder="./grain_test",
    kv: AlabamaKv = None,
    bitrate=-1,
    crf=20,
    video_filters: str = "",
) -> int:
    cache_key = "best_sequence_grain"

    if kv is not None:
        val = kv.get_global(cache_key)
        if val is not None:
            return int(val)

    if not os.path.exists(temp_folder):
        raise Exception(f"temp_folder {temp_folder} does not exist")

    # turn temp folder into a full path
    temp_folder = os.path.abspath(temp_folder)
    # make /adapt/grain dir
    os.makedirs(f"{temp_folder}/adapt/grain", exist_ok=True)

    if input_file is None:
        raise Exception("input_file is required")

    if scenes is None:
        raise Exception("scenes is required")
    # create a copy of the object, so it doesn't cause trouble
    scenes = copy.deepcopy(scenes)

    print("starting autograin test")

    if len(scenes.chunks) > 10:
        # bases on length, remove every x scene from the list so its shorter
        scenes.chunks = scenes.chunks[:: int(len(scenes.chunks) / 10)]

    random.seed(2)
    random.shuffle(scenes.chunks)

    chunks_for_processing = scenes.chunks[:6]

    jobs = [
        {
            "chunk": chunk,
            "encoded_scene_path": f"{temp_folder}/adapt/grain/{chunk.chunk_index}",
            "crf": crf,
            "bitrate": bitrate,
            "vf": video_filters,
        }
        for chunk in chunks_for_processing
    ]

    # parallelize the butteraugli tests
    with ThreadPool() as p:
        results = p.map(wrapper, jobs)
        p.close()
        p.join()

    # get the results
    ideal_grain = int(mean(results))
    print(f"for 6 random scenes, the average ideal grain is {ideal_grain}")
    if kv is not None:
        kv.set_global(cache_key, ideal_grain)
    return ideal_grain
