"""
Class that decides the best: grain, some encoding parameters, average bitrate for a video file
In comparison to Adaptive command, this should only be run once per video. Adaptive command is run per chunk.
"""
import os.path
import pickle
import time

from alabamaEncode.adaptiveEncoding.sub.bitrateLadder import AutoBitrateLadder
from alabamaEncode.adaptiveEncoding.sub.grain import get_best_avg_grainsynth
from alabamaEncode.encoders import EncoderConfig
from alabamaEncode.sceneSplit.Chunks import ChunkSequence


def do_adaptive_analasys(
    chunk_sequence: ChunkSequence,
    config: EncoderConfig,
    do_grain=True,
    do_bitrate_ladder=False,
    do_crf=False,
):
    print("Starting adaptive content analysis")
    os.makedirs(f"{config.temp_folder}/adapt/", exist_ok=True)

    if os.path.exists(f"{config.temp_folder}/adapt/configCache.pt"):
        try:
            config = pickle.load(
                open(f"{config.temp_folder}/adapt/configCache.pt", "rb")
            )
            print("Loaded adaptive content analasys from cache")
        except:
            pass
    else:
        start = time.time()
        if config.flag1:
            ab = AutoBitrateLadder(chunk_sequence, config)

            if config.flag2:
                config.bitrate = ab.get_best_bitrate()

            config.crf = ab.get_target_crf(config.bitrate)

        else:
            ab = AutoBitrateLadder(chunk_sequence, config)

            if do_bitrate_ladder and not do_crf:
                config.bitrate = ab.get_best_bitrate()

            if config.convexhull and not do_crf:
                config.ssim_db_target = ab.get_target_ssimdb(config.bitrate)

            if do_grain and config.encoder.supports_grain_synth():
                param = {
                    "input_file": chunk_sequence.input_file,
                    "scenes": chunk_sequence,
                    "temp_folder": config.temp_folder,
                    "cache_filename": config.temp_folder + "/adapt/ideal_grain.pt",
                    "scene_pick_seed": 2,
                    "video_filters": config.crop_string,
                }
                if config.crf_bitrate_mode:
                    param["crf"] = config.crf
                else:
                    param["bitrate"] = config.bitrate

                config.grain_synth = get_best_avg_grainsynth(**param)

            # if do_qm and config.encoder == EncodersEnum.SVT_AV1:
            #     ab = AutoParam(chunk_sequence, config)
            #
            #     best_qm = ab.get_best_qm()
            #
            #     config.qm_enabled = best_qm["qm"]
            #     config.qm_min = best_qm["qm_min"]
            #     config.qm_max = best_qm["qm_max"]

            config.qm_enabled = True
            config.qm_min = 0
            config.qm_max = 7

        pickle.dump(config, open(f"{config.temp_folder}/adapt/configCache.pt", "wb"))
        time_taken = int(time.time() - start)
        print(f"Finished adaptive content analysis in {time_taken}s. Caching results")

    return config, chunk_sequence
