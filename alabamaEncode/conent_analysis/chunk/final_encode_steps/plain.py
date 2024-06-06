from alabamaEncode.conent_analysis.chunk.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.chunk import ChunkObject


class PlainFinalEncode(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        metric, _ = ctx.get_metric_target()
        stats = enc.run(
            metric_to_calculate=metric if ctx.calc_final_vmaf else None,
            metric_params=ctx.get_vmaf_options(),
            on_frame_encoded=encoded_a_frame,
        )
        if metric == Metric.VMAF and ctx.calc_final_vmaf:
            if stats.metric_results.frames is not None:
                vmaf_frame_scores = {}
                for frame in stats.metric_results.frames:
                    vmaf_frame_scores[frame["frameNum"]] = frame["metrics"]["vmaf"]
                ctx.get_kv().set(
                    "vmaf_frame_scores",
                    chunk.chunk_index,
                    vmaf_frame_scores,
                    individual_mode=True,
                )

        return stats

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        joined = " && ".join(enc.get_encode_commands())
        return joined
