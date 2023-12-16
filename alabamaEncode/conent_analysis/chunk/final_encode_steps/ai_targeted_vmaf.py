import copy
import os

from tqdm import tqdm

from alabamaEncode.ai_vmaf.perdict import predict_crf
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


class AiTargetedVmafFinalEncode(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        vmaf_error_epsilon = 0.3

        def get_complexity(enc, c: ChunkObject):
            _enc = copy.deepcopy(enc)
            _enc.chunk = c
            _enc.speed = 12
            _enc.passes = 1
            _enc.rate_distribution = EncoderRateDistribution.CQ
            _enc.crf = 16
            _enc.threads = 1
            _enc.grain_synth = 0
            _enc.output_path = (
                f"/tmp/{c.chunk_index}_complexity{_enc.get_chunk_file_extension()}"
            )
            stats = _enc.run()
            from math import log

            formula = log(stats.bitrate)
            # self.config.log(
            #     f"[{c.chunk_index}] complexity: {formula:.2f} in {stats.time_encoding}s"
            # )
            os.remove(_enc.output_path)
            return c.chunk_index, formula

        # vmafmotion = Ffmpeg.get_vmaf_motion(chunk)
        # compexity = get_complexity(copy.deepcopy(enc), chunk)[1]
        # crf = get_crf_for_vmaf(
        #     model_path="/home/kokoniara/dev/VideoSplit/alabamaEncode/experiments/crf_vmaf_relation/latest.keras",
        #     vmaf_motion=vmafmotion,
        #     complexity=compexity,
        #     vmaf_target=ctx.vmaf,
        # )

        enc.crf = predict_crf(chunk, ctx.prototype_encoder.video_filters)
        tqdm.write(chunk.log_prefix() + f"trying Ai perdicted crf {enc.crf}")

        vmaf_options = VmafOptions(
            uhd=ctx.vmaf_4k_model,
            phone=ctx.vmaf_phone_model,
            ref=ComparisonDisplayResolution.from_string(ctx.vmaf_reference_display)
            if ctx.vmaf_reference_display
            else None,
            no_motion=ctx.vmaf_no_motion,
        )
        trys_for_interpolation = []
        first_try_stat = enc.run(
            calculate_vmaf=True,
            vmaf_params=vmaf_options,
        )

        if abs(first_try_stat.vmaf - ctx.vmaf) > vmaf_error_epsilon:
            tqdm.write(
                chunk.log_prefix()
                + f"Ai perdicted vmaf {first_try_stat.vmaf} is too far from target {ctx.vmaf},"
                f" trying binary search"
            )
            trys_for_interpolation.append((enc.crf, first_try_stat.vmaf_result.mean))
        else:
            for i in range(chunk.get_frame_count()):
                encoded_a_frame(-1, -1, -1)
            return first_try_stat

        # binary search

        from alabamaEncode.adaptive.helpers.probe_file_path import get_probe_file_base

        def log_to_convex_log(_str):
            if ctx.log_level >= 2:
                tqdm.write(_str)
            with open(os.path.join(ctx.temp_folder, "convex.log"), "a") as f:
                f.write(_str + "\n")

        probe_file_base = get_probe_file_base(chunk.chunk_path)
        low_crf = 20 if isinstance(enc, EncoderSvt) else 10
        high_crf = 55
        if ctx.vmaf < 90:
            high_crf = 63

        max_probes = 2

        mid_crf = 0
        depth = 0

        original_path = enc.output_path

        while low_crf <= high_crf and depth < max_probes:
            mid_crf = (low_crf + high_crf) // 2

            # don't try the same crf twice
            if mid_crf in [t[0] for t in trys_for_interpolation]:
                break

            enc.crf = mid_crf
            enc.output_path = os.path.join(
                probe_file_base,
                f"convexhull.{mid_crf}{enc.get_chunk_file_extension()}",
            )
            enc.speed = ctx.probe_speed_override
            enc.passes = 1
            enc.threads = 1
            enc.grain_synth = 0
            enc.override_flags = None
            stats: EncodeStats = enc.run(
                calculate_vmaf=True,
                vmaf_params=vmaf_options,
            )

            log_to_convex_log(
                f"{chunk.log_prefix()} crf: {mid_crf} vmaf: {stats.vmaf_result.mean} "
                f"bitrate: {stats.bitrate} attempt {depth}/{max_probes}"
            )

            if abs(stats.vmaf_result.mean - ctx.vmaf) <= vmaf_error_epsilon:
                # move the probe to original_path and return stats
                os.rename(enc.output_path, original_path)
                return stats
            elif stats.vmaf_result.mean > ctx.vmaf:
                low_crf = mid_crf + 1
            else:
                high_crf = mid_crf - 1
            trys_for_interpolation.append((mid_crf, stats.vmaf_result.mean))
            depth += 1

        # via linear interpolation, find the crf that is closest to target vmaf
        if len(trys_for_interpolation) > 1:
            points = sorted(trys_for_interpolation, key=lambda x: abs(x[1] - ctx.vmaf))
            low_point = points[0]
            high_point = points[1]
            crf_low = low_point[0]
            crf_high = high_point[0]
            vmaf_low = low_point[1]
            vmaf_high = high_point[1]
            if (
                not vmaf_high - vmaf_low == 0
            ):  # means multiple probes got the same score, aka all back screen etc
                interpolated_crf = crf_low + (crf_high - crf_low) * (
                    (ctx.vmaf - vmaf_low) / (vmaf_high - vmaf_low)
                )

                clamp_low = min(crf_low, crf_high) - 2
                clamp_high = max(crf_low, crf_high) + 2

                # eg. 25-30 are crf points closes to target, so we clamp the interpolated crf to 23-32
                interpolated_crf = max(min(interpolated_crf, clamp_high), clamp_low)

                if enc.supports_float_crfs():
                    interpolated = interpolated_crf
                else:
                    interpolated = int(interpolated_crf)
            else:
                interpolated = mid_crf
        else:
            interpolated = mid_crf

        log_to_convex_log(f"{chunk.log_prefix()} interpolated crf: {interpolated}")

        enc.crf = interpolated
        return enc.run(
            calculate_vmaf=True,
            vmaf_params=vmaf_options,
            on_frame_encoded=encoded_a_frame,
        )

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception("dry_run not implemented for AiTargetedVmafFinalEncode")
