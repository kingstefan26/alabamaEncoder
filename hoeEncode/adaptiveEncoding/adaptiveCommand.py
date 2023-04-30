from hoeEncode.adaptiveEncoding.sub.bitrate import AutoBitrate
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
    final_encode_timeout = 600

    calc_final_vmaf = False

    def run(self):
        bitrate = AutoBitrate(chunk=self.chunk, config=self.config)

        enc = AbstractEncoderSvtenc()
        enc.eat_job_config(job=self.job, config=self.config)
        enc.update(
            passes=self.config.passes,
            svt_grain_synth=self.config.grain_synth,
            bitrate=bitrate.get_ideal_bitrate(),
            rate_distribution=RateDistribution.VBR,
            speed=self.config.speed
        )
        enc.bias_pct = 20

        try:
            stats: EncoderStats = enc.run(timeout_value=self.final_encode_timeout, calculate_vmaf=self.calc_final_vmaf)
            print(
                f'[{self.job.chunk.chunk_index}] final stats:'
                f' vmaf={stats.vmaf} '
                f' time={stats.time_encoding}s '
                f' bitrate={stats.time_encoding}k'
            )
        except Exception as e:
            print(f'[{self.job.chunk.chunk_index}] error while encoding: {e}')
