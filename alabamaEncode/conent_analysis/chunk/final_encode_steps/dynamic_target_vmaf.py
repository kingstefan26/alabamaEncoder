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
import os
from typing import Tuple

from alabamaEncode.conent_analysis.chunk.final_encode_steps.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.impl.Aomenc import EncoderAom
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.scene.chunk import ChunkObject


class DynamicTargetVmaf(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        metric_target = ctx.vmaf

        def get_metric_from_stats(_stats: EncodeStats) -> float:
            """
            this class assumes a metric that's scale is 0-100
            """
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

        def get_score(_stats: EncodeStats) -> float:
            """
            Score to minimize

            formula so that after ~1Mb/s & 12 frames we start to exponentially add weight,
            taking frames and bitrate into account will make sure that
            short high bitrate blips will mostly get ignored,
            but longer larger bitrates will be penalised
            at about 10Mb/s & 48 frames the weight will be ~5,
            so for example, 10Mb/s for 48 frames will have the same impact as a vmaf error of 5
            The overall goal is get greedy with bitrate while being guided by vmaf,
            because pure vmaf guidance can lead to keeping a lot of unnecessary grain on motionless scenes,
            exacerbated on low quality sources
            """

            if not (isinstance(enc, EncoderSvt) or isinstance(enc, EncoderAom)):
                print(
                    f"{self.__class__.__name__} is tuned for AV1 codecs, expect suboptimal results"
                )

            metric = get_metric_from_stats(_stats)
            frames = _stats.length_frames
            bitrate = _stats.bitrate  # in kbps

            # bitrate component
            bitrate_weight = (bitrate / 650) ** 0.4 - 1
            bitrate_weight *= 2

            # Exponential component for the number of frames
            size_kb = (frames * bitrate) / 1000
            overall_size_weight = (size_kb / 250) ** 0.5
            overall_size_weight = max(overall_size_weight, 1)

            # Combine the components
            combined_weight = bitrate_weight * overall_size_weight

            # Ensure the combined weight is not negative
            combined_weight = max(combined_weight, 0)
            return abs(metric_target - metric) + combined_weight

        def log(_str):
            ctx.log(
                f"{chunk.log_prefix()}{_str}",
                category="probe",
            )

        original_speed = enc.speed
        original_output_path = enc.output_path
        trys = []
        stats = None

        def finish(_stats, crf):
            log(
                f"Finished with crf {crf}; {metric_name}: {get_metric_from_stats(_stats)};"
                f" score_error: {get_score(_stats)}; bitrate: {_stats.bitrate} kb/s"
            )
            ctx.get_kv().set("best_crfs", chunk.chunk_index, crf)
            os.rename(enc.output_path, original_output_path)
            return _stats

        metric_name = "vmaf"

        tries = 0
        max_tries = 10

        def run_probe(crf) -> Tuple[float, EncodeStats, float, float]:
            """
            :param crf: crf to try
            :param run_faster_speed: to run at faster speed for initial search probes
            :return: [vmaf error, stats, vmaf]
            """
            enc.crf = crf
            enc.output_path = os.path.join(
                probe_file_base,
                f"{chunk.chunk_index}_{enc.crf}{enc.get_chunk_file_extension()}",
            )
            nonlocal stats
            stats = enc.run(
                calculate_vmaf=True,
                vmaf_params=ctx.get_vmaf_options(),
            )
            _metric = get_metric_from_stats(stats)
            _score = get_score(stats)

            nonlocal tries
            log(
                f"crf: {crf}; {metric_name}: {_metric}; score_error: {_score}; bitrate: {stats.bitrate} kb/s; "
                f"attempt {tries}/{max_tries}"
            )
            trys.append((abs(metric_target - _metric), stats, _metric, _score, crf))
            return abs(metric_target - _metric), stats, _metric, _score

        probe_file_base = ctx.get_probe_file_base(chunk.chunk_path)

        enc.output_path = os.path.join(
            probe_file_base,
            f"{chunk.chunk_index}{enc.get_chunk_file_extension()}",
        )
        enc.passes = 1
        enc.rate_distribution = EncoderRateDistribution.CQ

        low_crf = 18 if isinstance(enc, EncoderSvt) else 12
        high_crf = 55
        max_score_error = 0.7

        tol = 0.10 if enc.supports_float_crfs() else 1
        gr = (1 + 5**0.5) / 2

        a = high_crf - (high_crf - low_crf) / gr
        b = low_crf + (high_crf - low_crf) / gr

        a = round(a) if not enc.supports_float_crfs() else a
        b = round(b) if not enc.supports_float_crfs() else b

        current_metric_error_a, stats_a, metric_a, score_a = run_probe(a)

        if score_a < max_score_error:
            return finish(stats_a, a)

        current_metric_error_b, stats_b, metric_b, score_b = run_probe(b)

        if score_b < max_score_error:
            return finish(stats_b, b)

        tries += 2

        while abs(high_crf - low_crf) > tol and tries < max_tries:
            tries += 1

            if score_a < score_b:
                high_crf = b
                b = a
                stats_b = stats_a
                score_b = score_a
                current_metric_error_b = current_metric_error_a
                metric_b = metric_a
                a = high_crf - (high_crf - low_crf) / gr
                a = round(a) if not enc.supports_float_crfs() else a

                # check if we already tried this crf
                if any([abs(_x[4] - a) < 0.1 for _x in trys]):
                    log(f"crf {a} already tried, quiting")
                    return finish(stats_a, a)

                current_metric_error_a, stats_a, metric_a, score_a = run_probe(a)
                if score_a < max_score_error:
                    return finish(stats_a, a)
            else:
                low_crf = a
                a = b
                stats_a = stats_b
                metric_a = metric_b
                score_a = score_b
                b = low_crf + (high_crf - low_crf) / gr
                b = round(b) if not enc.supports_float_crfs() else b

                # check if we already tried this crf
                if any([abs(_x[4] - b) < 0.1 for _x in trys]):
                    log(f"crf {b} already tried, quiting")
                    return finish(stats_b, b)

                current_metric_error_b, stats_b, metric_b, score_b = run_probe(b)
                if score_b < max_score_error:
                    return finish(stats_b, b)

            # Check if the probe score is within the error
            if max_score_error > score_a or max_score_error > score_b:
                # Log the result and quit early
                log(
                    f"Probe score({min(score_a, score_b)}) within error ({metric_name} "
                    f"err: {min(current_metric_error_a, current_metric_error_b)})"
                    f" {min(stats_a.bitrate, stats_b.bitrate)} kb/s, quiting early"
                )
                # Return the result
                if score_a < score_b:
                    return finish(stats_a, a)
                else:
                    return finish(stats_b, b)

        # Return the middle point of the search interval as the answer
        last_crf_try = (low_crf + high_crf) / 2
        last_crf_try = (
            round(last_crf_try) if not enc.supports_float_crfs() else last_crf_try
        )

        # check if we already tried this crf
        if any([abs(_x[4] - last_crf_try) < 0.1 for _x in trys]):
            log(f"crf {last_crf_try} already tried, quiting")
            return finish(stats_a, last_crf_try)

        current_metric_error, stats, metric, score = run_probe(last_crf_try)
        log(
            f"crf: {last_crf_try} {metric_name}: {metric} score_error: {score} "
            f"attempt {tries}/{max_tries}"
        )
        return finish(stats, last_crf_try)

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception(f"dry_run not implemented for {self.__class__.__name__}")
