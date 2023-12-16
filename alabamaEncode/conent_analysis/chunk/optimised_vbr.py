from alabamaEncode.conent_analysis.chunk_analyse_pipeline_item import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.scene.chunk import ChunkObject


class VbrPerChunkOptimised(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        from alabamaEncode.adaptive.helpers.bitrate import get_ideal_bitrate

        enc.rate_distribution = EncoderRateDistribution.VBR
        enc.bitrate = get_ideal_bitrate(chunk, ctx)
        enc.passes = 3
        enc.svt_bias_pct = 20
        return enc
