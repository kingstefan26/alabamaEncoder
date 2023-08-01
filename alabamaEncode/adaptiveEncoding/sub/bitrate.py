import os
import pickle
import time

from alabamaEncode.adaptiveEncoding.util import get_probe_file_base
from alabamaEncode.encoders import EncoderConfig
from alabamaEncode.encoders.RateDiss import RateDistribution
from alabamaEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from alabamaEncode.ffmpegUtil import get_video_ssim
from alabamaEncode.sceneSplit.ChunkOffset import ChunkObject


def get_ideal_bitrate(
    chunk: ChunkObject,
    config: EncoderConfig,
    convex_speed=10,
    show_rate_calc_log=False,
    clamp_complexity=True,
) -> int:
    """
    Gets the ideal bitrate for a chunk
    """

    rate_search_start = time.time()

    probe_file_base = get_probe_file_base(chunk.chunk_path, config.temp_folder)
    cache_filename = f"{probe_file_base}.complexity.speed{convex_speed}.pt"

    ideal_rate = None

    # check if we have already done this
    if os.path.exists(cache_filename):
        try:
            ideal_rate = pickle.load(open(cache_filename, "rb"))
        except:
            print("Error loading complexity cache file, recalculating")

    if not ideal_rate:
        test_probe_path = f"{probe_file_base}complexity.probe.ivf"

        enc = AbstractEncoderSvtenc()

        enc.update(
            speed=convex_speed,
            passes=1,
            temp_folder=config.temp_folder,
            chunk=chunk,
            svt_grain_synth=0,
            current_scene_index=chunk.chunk_index,
            output_path=test_probe_path,
            threads=1,
            crop_string=config.crop_string,
            bitrate=config.bitrate,
            rate_distribution=RateDistribution.VBR,
        )

        enc.run(override_if_exists=False)

        try:
            (ssim, ssim_db) = get_video_ssim(
                test_probe_path, chunk, get_db=True, crop_string=config.crop_string
            )
        except Exception as e:
            print(f"Error calculating ssim for complexity rate estimation: {e}")
            # this happens when the scene is fully black, the best solution here is just setting the complexity to 0,
            # and since its all black anyway it won't matter
            ssim_db = config.ssim_db_target

        # Calculate the ratio between the target ssim dB and the current ssim dB
        ratio = 10 ** ((config.ssim_db_target - ssim_db) / 10)

        # Clamp the ratio to the complexity clamp
        if clamp_complexity:
            ratio = max(
                min(ratio, 1 + config.bitrate_overshoot), 1 - config.bitrate_undershoot
            )

        # Interpolate the ideal rate using the ratio
        ideal_rate = config.bitrate * ratio
        ideal_rate = int(ideal_rate)

        if show_rate_calc_log:
            print(
                f"{chunk.log_prefix()}===============\n"
                f"{chunk.log_prefix()} encode rate: {config.bitrate}k/s\n"
                f"{chunk.log_prefix()} ssim dB when using target bitrate: {ssim_db} (wanted: {config.ssim_db_target})\n"
                f"{chunk.log_prefix()} ratio = 10 ** (dB_target - dB) / 10 = {ratio}\n"
                f"{chunk.log_prefix()} ideal rate: max(min(encode_rate * ratio, upper_clamp), bottom_clamp) = {ideal_rate:.2f}k/s\n"
                f"{chunk.log_prefix()}==============="
            )

        try:
            pickle.dump(ideal_rate, open(cache_filename, "wb"))
        except:
            pass

    if ideal_rate == -1:
        raise Exception("ideal_rate is -1")

    config.log(
        f"{chunk.log_prefix()}rate search took: {int(time.time() - rate_search_start)}s, ideal bitrate: {ideal_rate}"
    )

    return int(ideal_rate)
