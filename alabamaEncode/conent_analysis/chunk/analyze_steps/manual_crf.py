from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.scene.chunk import ChunkObject


class CrfIndexesMap(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        crf_map = self.crf_map.split(",")

        if len(crf_map) < chunk.chunk_index:
            raise Exception(
                f"crf_map is too short, {len(crf_map)} < {chunk.chunk_index}"
            )

        enc.rate_distribution = EncoderRateDistribution.CQ
        enc.passes = 1
        try:
            enc.crf = int(crf_map[chunk.chunk_index])
        except ValueError:
            raise Exception(f"crf_map is not a list of ints: {self.crf_map}")
        enc.svt_tune = 0
        enc.svt_overlay = 0

        return enc

    def __init__(self, crf_map: str):
        self.crf_map = crf_map
