from alabamaEncode.conent_analysis.chunk.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.comparison_display import ComparisonDisplayResolution
from alabamaEncode.metrics.impl.xpsnr import XpsnrOptions
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.metrics.options import MetricOptions
from alabamaEncode.scene.chunk import ChunkObject


class PlainFinalEncode(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        metric, _ = ctx.get_metric_target()

        metric_options = MetricOptions()

        if metric == Metric.VMAF:
            metric_options = ctx.get_vmaf_options()
        elif metric == Metric.XPSNR:
            metric_options = XpsnrOptions(
                ref=(
                    ComparisonDisplayResolution.from_string(ctx.vmaf_reference_display)
                    if ctx.vmaf_reference_display
                    else None
                ),
                denoise_refrence=ctx.denoise_vmaf_ref,
                subsample=ctx.vmaf_subsample,
            )

        stats = enc.run(
            metric_to_calculate=metric if ctx.calc_final_vmaf else None,
            metric_params=metric_options,
            on_frame_encoded=encoded_a_frame,
        )

        if ctx.calc_final_vmaf and stats.metric_results.frames is not None:
            frame_scores = {}

            for frame in stats.metric_results.frames:
                if metric == Metric.VMAF:
                    frame_scores[frame["frameNum"]] = frame["metrics"]["vmaf"]
                if metric == Metric.XPSNR:
                    frame_scores[frame["frame"]] = frame["avg"]

            ctx.get_kv().set(
                "frame_scores",
                chunk.chunk_index,
                frame_scores,
                individual_mode=True,
            )

        return stats

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        joined = " && ".join(enc.get_encode_commands())
        return joined
