"""
Class that decides the best: grain, some encoding parameters, average bitrate for a video file
In comparison to Adaptive command, this should only be run once per video. Adaptive command is run per chunk.
"""
import os.path
import time

from alabamaEncode.adaptive.sub.bitrateLadder import AutoBitrateLadder
from alabamaEncode.adaptive.sub.grain import get_best_avg_grainsynth
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.scene.sequence import ChunkSequence


def analyze_content(
    chunk_sequence: ChunkSequence,
    ctx: AlabamaContext,
):
    os.makedirs(f"{ctx.temp_folder}/adapt/", exist_ok=True)

    start = time.time()
    ab = AutoBitrateLadder(chunk_sequence, ctx)

    if ctx.flag1:
        # if config.flag2:
        #     if config.flag3:
        #         config.bitrate = ab.get_best_bitrate_guided()
        #     else:
        #         config.bitrate = ab.get_best_bitrate()
        # config.crf = ab.get_target_crf(config.bitrate)

        ab.get_best_crf_guided()
    else:
        if ctx.crf == -1 and ctx.crf_based_vmaf_targeting is False:
            if ctx.find_best_bitrate:
                ctx.bitrate = ab.get_best_bitrate()

            if ctx.vbr_perchunk_optimisation:
                ctx.ssim_db_target = ab.get_target_ssimdb(ctx.bitrate)

    if ctx.find_best_grainsynth and ctx.encoder.supports_grain_synth():
        param = {
            "input_file": chunk_sequence.input_file,
            "scenes": chunk_sequence,
            "temp_folder": ctx.temp_folder,
            "cache_filename": ctx.temp_folder + "/adapt/ideal_grain.pt",
            "scene_pick_seed": 2,
            "video_filters": ctx.video_filters,
        }
        if ctx.crf_bitrate_mode:
            param["crf"] = ctx.crf
        else:
            param["bitrate"] = ctx.bitrate

        ctx.grain_synth = get_best_avg_grainsynth(**param)

    ctx.qm_enabled = True
    ctx.qm_min = 0
    ctx.qm_max = 7

    if ctx.grain_synth == 0 and ctx.bitrate < 2000:
        print("Film grain less then 0 and bitrate is low, overriding to 2 film grain")
        ctx.film_grain = 2

    if os.path.exists(f"{ctx.temp_folder}/adapt/"):
        if not os.listdir(f"{ctx.temp_folder}/adapt/"):
            os.rmdir(f"{ctx.temp_folder}/adapt/")

    print(f"content analasys took: {int(time.time() - start)}s")
