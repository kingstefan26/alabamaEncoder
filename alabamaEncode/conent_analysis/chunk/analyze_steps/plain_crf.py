from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.scene.chunk import ChunkObject


class PlainCrf(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc.rate_distribution = EncoderRateDistribution.CQ
        enc.crf = ctx.prototype_encoder.crf
        enc.passes = 1
        return enc
