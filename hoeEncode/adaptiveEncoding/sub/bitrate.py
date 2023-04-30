import os
import pickle
import time

from hoeEncode.adaptiveEncoding.util import get_probe_file_base
from hoeEncode.encoders import EncoderConfig
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import get_video_ssim
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject


class AutoBitrate:

    def __init__(self, chunk: ChunkObject, config: EncoderConfig):
        self.chunk = chunk
        self.config: EncoderConfig = config

    # what speed do we run while searching bitrate
    convex_speed = 10

    show_rate_calc_log = False

    complexity_clamp_down = 0.5
    complexity_clamp_up = 0.35
    clamp_complexity = True

    def complexity_rate_estimation(self, ignore_cache=False):
        probe_file_base = get_probe_file_base(self.chunk.chunk_path, self.config.temp_folder)
        cache_filename = f'{probe_file_base}.complexity.speed{self.convex_speed}.pt'

        # check if we have already done this
        if os.path.exists(cache_filename) and ignore_cache is False:
            return pickle.load(open(cache_filename, 'rb'))

        test_probe_path = f'{probe_file_base}complexity.probe.ivf'

        enc = AbstractEncoderSvtenc()

        enc.update(speed=self.convex_speed,
                   passes=1,
                   temp_folder=self.config.temp_folder,
                   chunk=self.chunk,
                   svt_grain_synth=0,
                   current_scene_index=self.chunk.chunk_index,
                   output_path=test_probe_path,
                   threads=2,
                   crop_string=self.config.crop_string,
                   bitrate=self.config.bitrate,
                   rate_distribution=RateDistribution.VBR)

        enc.run(override_if_exists=False)

        try:
            (ssim, ssim_db) = get_video_ssim(test_probe_path, self.chunk, get_db=True,
                                             crop_string=self.config.crop_string)
        except Exception as e:
            print(f'Error calculating ssim for complexity rate estimation: {e}')
            # this happens when the scene is fully black, the best solution here is just setting the complexity to 0,
            # and since its all black anyway it won't matter
            ssim_db = self.config.ssim_db_target

        # Calculate the ratio between the target ssim dB and the current ssim dB
        ratio = 10 ** ((self.config.ssim_db_target - ssim_db) / 10)

        # Clamp the ratio to the complexity clamp
        if self.clamp_complexity:
            ratio = max(min(ratio, 1 + self.complexity_clamp_up), 1 - self.complexity_clamp_down)

        # Interpolate the ideal encode rate using the ratio
        ideal_rate = self.config.bitrate * ratio
        ideal_rate = int(ideal_rate)

        if self.show_rate_calc_log:
            print(
                f'{self.chunk.log_prefix()}===============\n'
                f'{self.chunk.log_prefix()} encode rate: {self.config.bitrate}k/s\n'
                f'{self.chunk.log_prefix()} ssim dB when using target bitrate: {ssim_db} (wanted: {self.config.ssim_db_target})\n'
                f'{self.chunk.log_prefix()} ratio = 10 ** (dB_target - dB) / 10 = {ratio}\n'
                f'{self.chunk.log_prefix()} ideal rate: max(min(encode_rate * ratio, upper_clamp), bottom_clamp) = {ideal_rate:.2f}k/s\n'
                f'{self.chunk.log_prefix()}==============='
            )

        # if self.remove_probes:
        #     os.remove(test_probe_path)

        pickle.dump(ideal_rate, open(cache_filename, 'wb'))
        return ideal_rate

    def get_ideal_bitrate(self) -> int:

        rate_search_start = time.time()

        ideal_rate = self.complexity_rate_estimation()

        if ideal_rate == -1:
            raise Exception('ideal_rate is -1')

        print(
            f'{self.chunk.log_prefix()}rate search took: {int(time.time() - rate_search_start)}s, ideal bitrate: {ideal_rate}'
        )

        return int(ideal_rate)
