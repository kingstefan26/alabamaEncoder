from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.scene.chunk import ChunkObject


class PlainVbr(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc.rate_distribution = EncoderRateDistribution.VBR
        enc.bitrate = ctx.prototype_encoder.bitrate
        enc.passes = 3
        return enc
