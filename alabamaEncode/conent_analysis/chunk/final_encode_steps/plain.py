from alabamaEncode.conent_analysis.chunk.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.metric import Metrics
from alabamaEncode.scene.chunk import ChunkObject


class PlainFinalEncode(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        return enc.run(
            metric_to_calculate=Metrics.VMAF if not ctx.dont_calc_final_vmaf else None,
            metric_params=ctx.get_vmaf_options(),
            on_frame_encoded=encoded_a_frame,
        )

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        joined = " && ".join(enc.get_encode_commands())
        return joined
