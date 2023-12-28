import copy
import os

from alabamaEncode.conent_analysis.chunk.final_encode_steps.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.scene.chunk import ChunkObject


class DynamicTargetVmafVBR(FinalEncodeStep):
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

        enc.passes = 3
        enc.rate_distribution = EncoderRateDistribution.VBR

        def get_score(_bitrate):
            enc.bitrate = _bitrate
            enc.output_path = os.path.join(
                probe_file_base,
                f"convexhull.{_bitrate}{enc.get_chunk_file_extension()}",
            )
            enc.speed = min(max(ctx.prototype_encoder.speed + 2, 5), original.speed)
            stats: EncodeStats = enc.run(
                calculate_vmaf=True,
                vmaf_params=vmaf_options,
                override_if_exists=False,
            )
            return get_statistical_rep(stats), enc.output_path, stats

        low_bitrate = 100
        low_bitrate_cap = 100
        high_bitrate = 5000
        high_bitrate_cap = 20_000
        target_vmaf = ctx.vmaf
        vmaf_max_error = 0.7
        current_vmaf_error = 100
        depth = 0
        max_depth = 3
        trys = []
        mid_bitrate = 2000
        # even tho its "best_crfs" store bitrates
        if len(ctx.best_crfs) > 2:
            # set the mean of the best crf's so far as the first guess
            mid_bitrate = int(sum(ctx.best_crfs) / len(ctx.best_crfs))

            ctx.log(
                f"{chunk.log_prefix()}overriding first attempt to {mid_bitrate}",
                category="probe",
            )

        while current_vmaf_error > vmaf_max_error and depth < max_depth:
            if depth > 0:
                mid_bitrate = (low_bitrate + high_bitrate) // 2

            depth += 1
            mid_vmaf, probe_path, stats = get_score(mid_bitrate)
            trys.append((mid_bitrate, mid_vmaf))
            current_vmaf_error = abs(target_vmaf - mid_vmaf)
            ctx.log(
                f"{chunk.log_prefix()}bitrate: {mid_bitrate} vmaf: {mid_vmaf} vmaf_error: {current_vmaf_error}"
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
                os.rename(probe_path, original.output_path)
                ctx.best_crfs.append(mid_bitrate)
                return stats

            # check if two probes had the same vmaf, if so quit early since its prob a black screen
            if len(trys) > 1 and trys[-1][1] == trys[-2][1]:
                ctx.log(
                    f"{chunk.log_prefix()}Two probes got the same vmaf, quiting early",
                    category="probe",
                )
                # move to the original path
                os.rename(probe_path, original.output_path)
                return stats

            if mid_vmaf < target_vmaf:
                low_bitrate = mid_bitrate
            else:
                high_bitrate = mid_bitrate

        interpol_steps = 3

        for interpol_step in range(interpol_steps):
            # sort by vmaf difference from target
            points = sorted(trys, key=lambda _x: abs(_x[1] - target_vmaf))

            # get the two closest points
            bitrate_low, vmaf_low = points[0]
            bitrate_high, vmaf_high = points[1]

            # if the diffrence bettwen vmaf_low and vmaf_high is less then vmaf_high and vmaf_highhigh,
            # then use the highhigh point instead of the low point
            if len(points) > 2:
                if abs(vmaf_low - vmaf_high) < abs(vmaf_high - points[2][1]):
                    bitrate_high, vmaf_high = points[2]

            interpolated_bitrate = bitrate_low + (bitrate_high - bitrate_low) * (
                (target_vmaf - vmaf_low) / (vmaf_high - vmaf_low)
            )

            interpolated_bitrate = max(
                min(interpolated_bitrate, high_bitrate_cap), low_bitrate_cap
            )

            # quit early if interpolated crf is in trys
            if any([abs(_x[0] - interpolated_bitrate) < 25 for _x in trys]):
                ctx.log(
                    f"{chunk.log_prefix()}Interpolate pass {interpol_step}: "
                    f"crf {interpolated_bitrate} already tried, quiting",
                    category="probe",
                )
                ctx.best_crfs.append(interpolated_bitrate)
                return interpolated_stats

            ctx.log(
                f"{chunk.log_prefix()}Interpolate pass {interpol_step}: bitrate {interpolated_bitrate}",
                category="probe",
            )

            enc.bitrate = interpolated_bitrate
            enc.speed = original.speed
            enc.output_path = original.output_path
            interpolated_stats = enc.run(calculate_vmaf=True, vmaf_params=vmaf_options)
            vmaf_result = get_statistical_rep(interpolated_stats)
            trys.append((interpolated_bitrate, vmaf_result))
            current_vmaf_error = abs(target_vmaf - vmaf_result)
            if current_vmaf_error > vmaf_max_error:
                ctx.log(
                    f"{chunk.log_prefix()}Interpolate pass {interpol_step}: "
                    f"bitrate {interpolated_bitrate} vmaf {vmaf_result}",
                    category="probe",
                )
            else:
                ctx.log(
                    f"{chunk.log_prefix()}Interpolate pass {interpol_step}: "
                    f"bitrate {interpolated_bitrate} vmaf {vmaf_result}, success, quiting",
                    category="probe",
                )
                ctx.best_crfs.append(interpolated_bitrate)
                return interpolated_stats

        ctx.log(
            f"{chunk.log_prefix()}Failed to hit target after {interpol_steps} steps, quiting",
            category="probe",
        )
        ctx.best_crfs.append(interpolated_bitrate)
        return interpolated_stats

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception(f"dry_run not implemented for {self.__class__.__name__}")
