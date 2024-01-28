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
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calc import get_metric_from_stats
from alabamaEncode.scene.chunk import ChunkObject


class TargetVmaf(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        original = copy.deepcopy(enc)

        target_vmaf = ctx.vmaf

        probe_file_base = ctx.get_probe_file_base(chunk.chunk_path)

        def get_score(_crf):
            enc.crf = _crf
            enc.output_path = os.path.join(
                probe_file_base,
                f"convexhull.{_crf}{enc.get_chunk_file_extension()}",
            )
            enc.speed = get_vmaf_probe_speed(enc)
            enc.passes = 1
            enc.threads = 1
            enc.grain_synth = 0
            enc.svt_tune = 0
            enc.override_flags = None
            stats: EncodeStats = enc.run(
                calculate_vmaf=True,
                vmaf_params=ctx.get_vmaf_options(),
                override_if_exists=False,
            )

            return get_metric_from_stats(
                stats=stats,
                statistical_representation=ctx.vmaf_target_representation,
            ) + get_vmaf_probe_offset(enc)

        probes = ctx.vmaf_probe_count
        trys = []
        low_crf, high_crf = get_crf_limits(enc.get_codec())
        epsilon = 0.1
        depth = 0
        mid_crf = 0
        while low_crf <= high_crf and depth < probes:
            mid_crf = (low_crf + high_crf) // 2

            # don't try the same crf twice
            if mid_crf in [t[0] for t in trys]:
                break

            statistical_representation = get_score(mid_crf)

            ctx.log(
                f"{chunk.log_prefix()} crf: {mid_crf} vmaf: {statistical_representation} "
                f"attempt {depth + 1}/{probes}",
                category="probe",
            )

            if abs(statistical_representation - target_vmaf) <= epsilon:
                break
            elif statistical_representation > target_vmaf:
                low_crf = mid_crf + 1
            else:
                high_crf = mid_crf - 1
            trys.append((mid_crf, statistical_representation))
            depth += 1

        # if we didn't get it right on the first,
        # via linear interpolation, try to find the crf that is closest to target vmaf
        if len(trys) > 1:
            # sort by vmaf difference from target
            points = sorted(trys, key=lambda _x: abs(_x[1] - target_vmaf))

            # get the two closest points
            crf_low, vmaf_low = points[0]
            crf_high, vmaf_high = points[1]

            # means multiple probes got the same score, aka all back screens etc
            if not vmaf_high - vmaf_low == 0:
                interpolated_crf = crf_low + (crf_high - crf_low) * (
                    (target_vmaf - vmaf_low) / (vmaf_high - vmaf_low)
                )

                # if 28-37 are crf points closes to target,
                # we clamp the interpolated crf to 18-41
                clamp_low = min(crf_low, crf_high) - 10
                clamp_high = max(crf_low, crf_high) + 4
                interpolated_crf = max(min(interpolated_crf, clamp_high), clamp_low)

                if enc.supports_float_crfs():
                    crf = interpolated_crf
                else:
                    crf = int(interpolated_crf)

                crf_min, crf_max = get_crf_limits(enc.get_codec())

                crf = max(min(crf, crf_max), crf_min)
            else:
                crf = mid_crf
        else:
            crf = mid_crf

        ctx.log(f"{chunk.log_prefix()}Decided on crf: {crf}", category="probe")

        enc.passes = 1
        enc.svt_tune = 0
        enc.svt_overlay = 0
        enc.rate_distribution = EncoderRateDistribution.CQ
        enc.crf = crf

        enc.output_path = chunk.chunk_path
        enc.override_flags = original.override_flags
        enc.speed = original.speed
        enc.grain_synth = original.grain_synth

        return enc
