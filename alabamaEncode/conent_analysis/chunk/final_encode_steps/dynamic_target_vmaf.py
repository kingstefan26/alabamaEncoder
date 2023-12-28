"""
Target vmaf but:
Do two probes at slightly faster speeds,
for each probe check if it's within the target, if its close enough, return it and quit early
if none passes the early quit do linear interpolation.
Encode at interpolated vmaf if it misses target by 1, redo interpolation but bicubic & encode
This yields a minimum of one encode, a maximum of 4 while being within the target
Most of the logic will be a copy of alabamaEncode/conent_analysis/chunk/target_vmaf.py,
but as a final encode step, so we can change output files
"""
import copy
import os

from alabamaEncode.conent_analysis.chunk.final_encode_steps.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.scene.chunk import ChunkObject


class DynamicTargetVmaf(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        def get_statistical_rep(_stats):
            match ctx.vmaf_target_representation:
                case "mean":
                    statistical_representation = _stats.vmaf_result.mean
                case "harmonic_mean":
                    statistical_representation = _stats.vmaf_result.harmonic_mean
                case "max":
                    statistical_representation = _stats.vmaf_result.max
                case "min":
                    statistical_representation = _stats.vmaf_result.min
                case "median":
                    statistical_representation = _stats.vmaf_result.percentile_50
                case "percentile_1":
                    statistical_representation = _stats.vmaf_result.percentile_1
                case "percentile_5":
                    statistical_representation = _stats.vmaf_result.percentile_5
                case "percentile_10":
                    statistical_representation = _stats.vmaf_result.percentile_10
                case "percentile_25":
                    statistical_representation = _stats.vmaf_result.percentile_25
                case "percentile_50":
                    statistical_representation = _stats.vmaf_result.percentile_50
                case _:
                    raise Exception(
                        f"Unknown vmaf_target_representation {ctx.vmaf_target_representation}"
                    )
            return statistical_representation

        original = copy.deepcopy(enc)
        vmaf_options = VmafOptions(
            uhd=ctx.vmaf_4k_model,
            phone=ctx.vmaf_phone_model,
            ref=ComparisonDisplayResolution.from_string(ctx.vmaf_reference_display)
            if ctx.vmaf_reference_display
            else None,
            no_motion=ctx.vmaf_no_motion,
        )

        from alabamaEncode.adaptive.helpers.probe_file_path import get_probe_file_base

        probe_file_base = get_probe_file_base(chunk.chunk_path)

        enc.output_path = os.path.join(
            probe_file_base,
            f"{chunk.chunk_index}{enc.get_chunk_file_extension()}",
        )

        enc.passes = 1
        enc.rate_distribution = EncoderRateDistribution.CQ

        low_crf = 10 if not isinstance(enc, EncoderSvt) else 18
        low_crf_cap = 10
        high_crf = 63
        high_crf_cap = 63
        target_vmaf = ctx.vmaf
        vmaf_max_error = 0.7
        current_vmaf_error = 100
        depth = 0
        max_depth = 2
        trys = []
        mid_crf = (low_crf + high_crf) // 2
        if len(ctx.best_crfs) > 2:
            # set the mean of the best crf's so far as the first guess
            mid_crf = int(sum(ctx.best_crfs) / len(ctx.best_crfs))

            ctx.log(
                f"{chunk.log_prefix()}overriding first attempt to {mid_crf}",
                category="probe",
            )

        while current_vmaf_error > vmaf_max_error and depth < max_depth:
            if depth > 0:
                mid_crf = (low_crf + high_crf) // 2

            depth += 1
            enc.crf = mid_crf
            enc.speed = min(max(ctx.prototype_encoder.speed + 2, 5), original.speed)
            stats: EncodeStats = enc.run(
                calculate_vmaf=True,
                vmaf_params=vmaf_options,
            )
            mid_vmaf = get_statistical_rep(stats)
            trys.append((mid_crf, mid_vmaf))
            current_vmaf_error = abs(target_vmaf - mid_vmaf)
            ctx.log(
                f"{chunk.log_prefix()}crf: {mid_crf} vmaf: {mid_vmaf} vmaf_error: {current_vmaf_error}"
                f" attempt {depth}/{max_depth}",
                category="probe",
            )
            if current_vmaf_error < vmaf_max_error:
                ctx.log(
                    f"{chunk.log_prefix()}Probe within error (vmaf err: {current_vmaf_error})"
                    f"{stats.bitrate} kb/s, quiting early",
                    category="probe",
                )
                # move to the original path
                ctx.best_crfs.append(mid_crf)
                os.rename(enc.output_path, original.output_path)
                return stats

            # check if two probes had the same vmaf, if so quit early since its prob a black screen
            if len(trys) > 1 and trys[-1][1] == trys[-2][1]:
                ctx.log(
                    f"{chunk.log_prefix()}Two probes got the same vmaf, quiting early",
                    category="probe",
                )
                # move to the original path
                os.rename(enc.output_path, original.output_path)
                print(f"MOVING {enc.output_path} -> {original.output_path}")
                return stats

            if mid_vmaf < target_vmaf:
                high_crf = mid_crf
            else:
                low_crf = mid_crf

        interpol_steps = 3

        for interpol_step in range(interpol_steps):
            # sort by vmaf difference from target
            points = sorted(trys, key=lambda _x: abs(_x[1] - target_vmaf))

            # get the two closest points
            crf_low, vmaf_low = points[0]
            crf_high, vmaf_high = points[1]

            if vmaf_low == vmaf_high:
                ctx.log(
                    f"{chunk.log_prefix()}Interpolate pass {interpol_step}: "
                    f"vmaflow{vmaf_low} == {vmaf_high}vmafhigh, quiting",
                    category="probe",
                )
                ctx.best_crfs.append(crf_low)
                os.rename(enc.output_path, original.output_path)
                print(f"MOVING {enc.output_path} -> {original.output_path}")
                return interpolated_stats

            interpolated_crf = crf_low + (crf_high - crf_low) * (
                (target_vmaf - vmaf_low) / (vmaf_high - vmaf_low)
            )

            # if 28-37 are crf points closes to target,
            # we clamp the interpolated crf to 18-41
            clamp_low = min(crf_low, crf_high) - 10
            clamp_high = max(crf_low, crf_high) + 4
            interpolated_crf = max(min(interpolated_crf, clamp_high), clamp_low)

            # clamp to binary search range
            interpolated_crf = max(min(interpolated_crf, high_crf_cap), low_crf_cap)

            # quit early if interpolated crf is in trys
            if any([abs(_x[0] - interpolated_crf) < 0.1 for _x in trys]):
                ctx.log(
                    f"{chunk.log_prefix()}Interpolate pass {interpol_step}: "
                    f"crf {interpolated_crf} already tried, quiting",
                    category="probe",
                )
                ctx.best_crfs.append(interpolated_crf)
                os.rename(enc.output_path, enc.output_path)
                return interpolated_stats

            if enc.supports_float_crfs():
                interpolated_crf = interpolated_crf
            else:
                interpolated_crf = int(interpolated_crf)

            ctx.log(
                f"{chunk.log_prefix()}Interpolate pass {interpol_step}: crf {interpolated_crf}",
                category="probe",
            )

            enc.crf = interpolated_crf
            enc.speed = original.speed
            interpolated_stats = enc.run(calculate_vmaf=True, vmaf_params=vmaf_options)
            vmaf_result = get_statistical_rep(interpolated_stats)
            trys.append((interpolated_crf, vmaf_result))
            current_vmaf_error = abs(target_vmaf - vmaf_result)
            if current_vmaf_error > vmaf_max_error:
                ctx.log(
                    f"{chunk.log_prefix()}Interpolate pass {interpol_step}: "
                    f"crf {interpolated_crf} vmaf {vmaf_result} {interpolated_stats.bitrate} kb/s",
                    category="probe",
                )
            else:
                ctx.log(
                    f"{chunk.log_prefix()}Interpolate pass {interpol_step}: "
                    f"crf {interpolated_crf} vmaf {vmaf_result} {interpolated_stats.bitrate} kb/s, success, quiting",
                    category="probe",
                )
                ctx.best_crfs.append(interpolated_crf)
                os.rename(enc.output_path, original.output_path)
                return interpolated_stats

        ctx.log(
            f"{chunk.log_prefix()}Failed to hit target after {interpol_steps} steps, quiting",
            category="probe",
        )
        ctx.best_crfs.append(interpolated_crf)
        os.rename(enc.output_path, original.output_path)
        return interpolated_stats

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception(f"dry_run not implemented for {self.__class__.__name__}")
