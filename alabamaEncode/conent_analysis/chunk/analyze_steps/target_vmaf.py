import copy
import os

from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.conent_analysis.opinionated_vmaf import (
    get_crf_limits,
    get_vmaf_probe_speed,
    get_vmaf_probe_offset,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calc import get_metric_from_stats
from alabamaEncode.scene.chunk import ChunkObject


class TargetVmaf(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc_copy = copy.deepcopy(enc)

        metric, target_metric = ctx.get_metric_target()

        probe_file_base = ctx.get_probe_file_base(chunk.chunk_path)

        def get_score(_crf):
            enc_copy.crf = _crf
            enc_copy.output_path = os.path.join(
                probe_file_base,
                f"probe.{_crf}{enc_copy.get_chunk_file_extension()}",
            )
            enc_copy.speed = get_vmaf_probe_speed(enc_copy)
            enc_copy.passes = 1
            enc_copy.threads = 1
            enc_copy.grain_synth = 0
            enc_copy.svt_tune = 0
            enc_copy.override_flags = None
            # TODO: calculate metrics outside enc.run to add the flexibility to calc other ones
            stats: EncodeStats = enc_copy.run(
                calculate_vmaf=True,
                vmaf_params=ctx.get_vmaf_options(),
                override_if_exists=False,
            )

            # TODO: offset the faster preset by metric amount
            return get_metric_from_stats(
                stats=stats,
                statistical_representation=ctx.vmaf_target_representation,
                metric=metric,
            ) + get_vmaf_probe_offset(enc_copy)

        probes = ctx.vmaf_probe_count
        trys = []
        low_crf, high_crf = get_crf_limits(enc_copy.get_codec())
        depth = 0
        mid_crf = 0
        while low_crf <= high_crf and depth < probes:
            mid_crf = (low_crf + high_crf) // 2

            # don't try the same crf twice
            if mid_crf in [t[0] for t in trys]:
                break

            statistical_representation = get_score(mid_crf)

            ctx.log(
                f"{chunk.log_prefix()} crf: {mid_crf} {metric.name}: {statistical_representation} "
                f"attempt {depth + 1}/{probes}",
                category="probe",
            )

            if statistical_representation > target_metric:
                low_crf = mid_crf + 1
            else:
                high_crf = mid_crf - 1

            trys.append((mid_crf, statistical_representation))
            depth += 1

        # if we didn't get it right on the first,
        # via linear interpolation, try to find the crf that is closest to target metric
        if len(trys) > 1:
            # sort by metric difference from target
            points = sorted(trys, key=lambda _x: abs(_x[1] - target_metric))

            # get the two closest points
            crf_low, metric_low = points[0]
            crf_high, metric_high = points[1]

            # means multiple probes got the same score, aka all back screens etc
            if not metric_high - metric_low == 0:
                crf = crf_low + (crf_high - crf_low) * (
                    (target_metric - metric_low) / (metric_high - metric_low)
                )

                if not enc_copy.supports_float_crfs():
                    crf = int(crf)

                crf_min, crf_max = get_crf_limits(enc_copy.get_codec())

                crf = max(min(crf, crf_max), crf_min)
            else:
                crf = mid_crf
        else:
            crf = mid_crf

        ctx.log(f"{chunk.log_prefix()}Decided on crf: {crf}", category="probe")

        enc.crf = crf

        return enc