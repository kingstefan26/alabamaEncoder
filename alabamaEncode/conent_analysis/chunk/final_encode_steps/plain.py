from alabamaEncode.conent_analysis.chunk.final_encode_steps.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.scene.chunk import ChunkObject


class PlainFinalEncode(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        return enc.run(
            calculate_vmaf=True,
            vmaf_params=VmafOptions(
                uhd=ctx.vmaf_4k_model,
                phone=ctx.vmaf_phone_model,
                ref=ComparisonDisplayResolution.from_string(ctx.vmaf_reference_display)
                if ctx.vmaf_reference_display
                else None,
                no_motion=ctx.vmaf_no_motion,
            ),
            on_frame_encoded=encoded_a_frame,
        )

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        joined = " && ".join(enc.get_encode_commands())
        return joined
