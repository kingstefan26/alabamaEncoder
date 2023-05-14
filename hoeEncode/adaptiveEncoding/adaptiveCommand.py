import os
import time

from tqdm import tqdm

from hoeEncode.adaptiveEncoding.sub.bitrate import get_ideal_bitrate
from hoeEncode.encoders import EncoderStats
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.parallelEncoding.Command import CommandObject


class AdaptiveCommand(CommandObject):
    """
    Class that gets the ideal bitrate and encodes the final chunk
    """

    def __init__(self):
        super().__init__()

    # how long (seconds) before we time out the final encoding
    # currently set to 10 minutes
    final_encode_timeout = 1000

    calc_final_vmaf = False

    run_on_celery = False

    def run(self):
        total_start = time.time()

        enc = AbstractEncoderSvtenc()

        enc.running_on_celery = self.run_on_celery

        enc.eat_job_config(job=self.job, config=self.config)
        if self.config.crf_bitrate_mode:
            enc.update(
                passes=1,
                svt_grain_synth=self.config.grain_synth,
                crf=self.config.crf,
                rate_distribution=RateDistribution.CQ_VBV,
                speed=self.config.speed,
                bitrate=self.config.bitrate
            )
            enc.open_gop = True
            enc.max_bitrate = self.config.max_bitrate
        else:
            enc.update(
                passes=3,
                svt_grain_synth=self.config.grain_synth,
                bitrate=get_ideal_bitrate(self.chunk, self.config),
                rate_distribution=RateDistribution.VBR,
                speed=self.config.speed
            )
            enc.bias_pct = 20

        try:
            stats: EncoderStats = enc.run(timeout_value=self.final_encode_timeout, calculate_vmaf=self.calc_final_vmaf)
            # round to two places
            total_fps = round(self.job.chunk.get_frame_count() / (time.time() - total_start), 2)

            # target bitrate vs actual bitrate diffrence in %
            taget_miss_proc = (stats.bitrate - enc.bitrate) / enc.bitrate * 100

            stats.total_fps = total_fps
            stats.target_miss_proc = taget_miss_proc
            stats.chunk_index = self.job.chunk.chunk_index
            tqdm.write(
                f'[{self.job.chunk.chunk_index}] final stats:'
                f' vmaf={stats.vmaf} '
                f' time={int(stats.time_encoding)}s '
                f' bitrate={stats.bitrate}k'
                f' bitrate_target_miss={taget_miss_proc:.2f}%'
                f' chunk_lenght={round(self.job.chunk.get_lenght(), 2)}s'
                f' total_fps={total_fps}'
            )
            # save the stats to [temp_folder]/stats/chunk_[index].json
            os.makedirs(f'{self.config.temp_folder}/stats', exist_ok=True)
            stats.save(f'{self.config.temp_folder}/stats/chunk_{self.job.chunk.chunk_index}.json')

        except Exception as e:
            print(f'[{self.job.chunk.chunk_index}] error while encoding: {e}')
