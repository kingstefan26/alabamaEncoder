from alabamaEncode.conent_analysis.chunk.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.scene.chunk import ChunkObject


class AiTargetedVmafFinalEncode(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        raise Exception("AiTargetedVmafFinalEncode not implemented")

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception("dry_run not implemented for AiTargetedVmafFinalEncode")
