"""
Class that decides the best: grain, some encoding parameters, average bitrate for a video file
In comparison to Adaptive command, this should only be run once per video. Adaptive command is run per chunk.
"""
import os.path
import time

from alabamaEncode.adaptive.sub.bitrateLadder import AutoBitrateLadder
from alabamaEncode.adaptive.sub.grain import get_best_avg_grainsynth
from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.sceneSplit.chunk import ChunkSequence


def do_adaptive_analasys(
    chunk_sequence: ChunkSequence,
    config: AlabamaContext,
):
    os.makedirs(f"{config.temp_folder}/adapt/", exist_ok=True)

    start = time.time()
    ab = AutoBitrateLadder(chunk_sequence, config)

    if config.flag1:
        # if config.flag2:
        #     if config.flag3:
        #         config.bitrate = ab.get_best_bitrate_guided()
        #     else:
        #         config.bitrate = ab.get_best_bitrate()
        # config.crf = ab.get_target_crf(config.bitrate)

        ab.get_best_crf_guided()
    else:
        if not (True if config.crf != -1 or config.flag2 else False):
            if config.find_best_bitrate:
                config.bitrate = ab.get_best_bitrate()

            if config.vbr_perchunk_optimisation:
                config.ssim_db_target = ab.get_target_ssimdb(config.bitrate)

    if config.find_best_grainsynth and config.encoder.supports_grain_synth():
        param = {
            "input_file": chunk_sequence.input_file,
            "scenes": chunk_sequence,
            "temp_folder": config.temp_folder,
            "cache_filename": config.temp_folder + "/adapt/ideal_grain.pt",
            "scene_pick_seed": 2,
            "video_filters": config.video_filters,
        }
        if config.crf_bitrate_mode:
            param["crf"] = config.crf
        else:
            param["bitrate"] = config.bitrate

        config.grain_synth = get_best_avg_grainsynth(**param)

    config.qm_enabled = True
    config.qm_min = 0
    config.qm_max = 7

    if config.grain_synth == 0 and config.bitrate < 2000:
        print("Film grain less then 0 and bitrate is low, overriding to 2 film grain")
        config.film_grain = 2

    if os.path.exists(f"{config.temp_folder}/adapt/"):
        if not os.listdir(f"{config.temp_folder}/adapt/"):
            os.rmdir(f"{config.temp_folder}/adapt/")

    print(f"content analasys took: {int(time.time() - start)}s")
