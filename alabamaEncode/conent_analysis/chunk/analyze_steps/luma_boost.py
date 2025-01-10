from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.scene.chunk import ChunkObject


class LumaBoost(ChunkAnalyzePipelineItem):
    def run(self, ctx, chunk: ChunkObject, enc: Encoder) -> Encoder:
        luma_boost = ctx.get_kv().get("luma_boost", chunk.chunk_path)

        if luma_boost is None:
            luma_boost = 0
            # logic here
            print(
                "DONT BE FOOLED, LUMA BOOST IS CURRENTLY A VOID NULL PLACEHOLDER FUNCTION"
            )
            enc.crf += luma_boost

            ctx.get_kv().set("luma_boost", chunk.chunk_path, luma_boost)
        else:
            enc.crf += luma_boost

        ctx.log(f"{chunk.log_prefix()}boosted luma by {luma_boost}", category="luma")

        return enc
