import os

from tqdm import tqdm

from alabamaEncode.conent_analysis.chunk.final_encode_step import FinalEncodeStep
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.scene.chunk import ChunkObject


class WeridCapedCrfFinalEncode(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        stats: EncodeStats = enc.run()

        if stats.bitrate > ctx.cutoff_bitrate:
            tqdm.write(
                chunk.log_prefix()
                + f"at crf {ctx.prototype_encoder.crf} got {stats.bitrate}, cutoff {ctx.cutoff_bitrate} k/s reached,"
                f" encoding three pass vbr at cutoff "
            )
        else:
            tqdm.write(
                chunk.log_prefix()
                + f"at crf {ctx.prototype_encoder.crf} got {stats.bitrate},"
                f" encoding three pass vbr at {stats.bitrate} k/s "
            )

        encode_bitrate = min(stats.bitrate, ctx.cutoff_bitrate)

        enc.passes = 3
        enc.rate_distribution = EncoderRateDistribution.VBR
        enc.bitrate = encode_bitrate
        os.remove(enc.output_path)
        stats: EncodeStats = enc.run(on_frame_encoded=encoded_a_frame)
        return stats

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception("dry_run not implemented for WeridCapedCrfFinalEncode")
