import copy
import os
import shutil

from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.conent_analysis.opinionated_vmaf import (
    get_crf_limits,
    get_vmaf_probe_speed,
    get_vmaf_probe_offset,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calculate import get_metric_from_stats
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.chunk import ChunkObject


class TargetVmaf(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc_copy = copy.deepcopy(enc)

        kv = ctx.get_kv()

        crf_from_kv = kv.get(bucket="target_vmaf", key=str(chunk.chunk_index))
        if crf_from_kv is not None:
            if enc.supports_float_crfs():
                enc.crf = float(crf_from_kv)
            else:
                enc.crf = int(crf_from_kv)
            return enc

        metric, target_metric = ctx.get_metric_target()

        probe_file_base = ctx.get_probe_file_base(chunk.chunk_path)

        def get_score(_crf):
            kv_key = f"{chunk.chunk_index}_{_crf}"
            result_from_kv = kv.get(bucket="target_vmaf_probes", key=kv_key)
            if result_from_kv is not None:
                return float(result_from_kv)

            enc_copy.crf = _crf
            enc_copy.output_path = os.path.join(
                probe_file_base,
                f"probe.{_crf}{enc_copy.get_chunk_file_extension()}",
            )
            enc_copy.speed = max(get_vmaf_probe_speed(enc_copy, ctx), enc.speed)
            enc_copy.override_flags = None
            # TODO: calculate metrics outside enc.run to add the flexibility to calc other ones
            stats: EncodeStats = enc_copy.run(
                metric_to_calculate=metric,
                metric_params=ctx.get_vmaf_options(),
                override_if_exists=False,
            )

            # TODO: offset the faster preset by metric amount
            result = get_metric_from_stats(
                stats=stats,
                statistical_representation=ctx.vmaf_target_representation,
            )
            if metric == Metric.VMAF:
                result += get_vmaf_probe_offset(enc_copy)

            kv.set(bucket="target_vmaf_probes", key=kv_key, value=result)
            return result

        probes = ctx.probe_count
        if probes > 3:
            ctx.log(
                f"probe count in TargetVmaf is set to {probes}, this is too high, <=3",
                level=1,
            )

        trys = []
        low_crf, high_crf = get_crf_limits(enc_copy, ctx)
        depth = 0
        mid_crf = 0
        while low_crf <= high_crf and depth < probes:
            mid_crf = (low_crf + high_crf) // 2

            if (depth == 2 and ctx.probe_count == 3) or (depth == 1 and ctx.probe_count == 2):
                ll, lh = get_crf_limits(enc_copy, ctx)
                m = (ll + lh) // 2
                # if closer to edge then the middle, use that edge
                if abs(mid_crf - ll) < abs(mid_crf - m):
                    mid_crf = ll
                else:
                    mid_crf = lh

                ctx.log(
                    f"{chunk.log_prefix()} skipping to crf edge: {mid_crf}",
                    category="probe",
                )
                
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

        # To limit the overhead, we do only 2-3 binary search probes.
        # It's too shallow to get a good result on its own,
        # that's why we can pick two close points and interpolate between them.
        # This improves prediction by a lot while only needing at ~3 probes
        if len(trys) > 1:
            # sort by metric difference from target
            points = sorted(trys, key=lambda _x: abs(_x[1] - target_metric))

            # get the two closest points
            crf_low, metric_low = points[0]
            crf_high, metric_high = points[1]

            # means multiple probes got the same score, aka all back screens etc
            if metric_high - metric_low == 0:
                crf = mid_crf
            else:
                crf = crf_low + (crf_high - crf_low) * (
                    (target_metric - metric_low) / (metric_high - metric_low)
                )

                if not enc_copy.supports_float_crfs():
                    crf = int(crf)

                crf_min, crf_max = get_crf_limits(enc_copy, ctx)

                crf = max(min(crf, crf_max), crf_min)
        else:
            crf = mid_crf

        ctx.log(f"{chunk.log_prefix()}Decided on crf: {crf}", category="probe")

        kv.set(bucket="target_vmaf", key=str(chunk.chunk_index), value=crf)

        # clean up probe folder
        if os.path.exists(probe_file_base):
            shutil.rmtree(probe_file_base)

        enc.crf = crf

        return enc
