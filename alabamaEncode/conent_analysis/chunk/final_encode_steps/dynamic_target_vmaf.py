import os
import shutil
from typing import Tuple

from alabamaEncode.conent_analysis.chunk.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.conent_analysis.opinionated_vmaf import get_crf_limits
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calculate import get_metric_from_stats
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.chunk import ChunkObject


def get_weighed_vmaf_score(
    _stats: EncodeStats,
    codec: Codec,
    statistical_representation: str,
    metric_target: float,
) -> float:
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

    if codec != Codec.av1:
        print(f"weighted vmaf is tuned for AV1 codecs, expect suboptimal results")

    metric = get_metric_from_stats(
        _stats, statistical_representation=statistical_representation
    )
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


class DynamicTargetVmaf(FinalEncodeStep):
    """
    Target vmaf but:
    we add a bitrate weight that was determined using some empirical observation
    now imagine a score, that is the vmaf error + the bitrate weight
    if we plot it against crf we get a U curve or more likely a nike swoosh
    we want to find the minimum of this curve
    binary search does not work because the curve is unimodal and were looking for the minimum.
    Alternatives are ternary search or golden section search
    This is a final encode step, since we will be running all encodes at the slow speed
    and then when we think its good enough we quit.
    We don't run probes at faster speeds because
    I've noticed that the vmaf calculation gives more overhead than actual encoding using reasonable SVTAV1 presets
    """

    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        metric_target = ctx.vmaf

        def log(_str):
            ctx.log(
                f"{chunk.log_prefix()}{_str}",
                category="probe",
            )

        original_speed = enc.speed
        original_output_path = enc.output_path
        probe_file_base = ctx.get_probe_file_base(chunk.chunk_path)
        trys = []
        stats = None

        def finish(_stats, crf):
            score_err = get_weighed_vmaf_score(
                stats,
                codec=enc.get_codec(),
                statistical_representation=ctx.vmaf_target_representation,
                metric_target=metric_target,
            )
            log(
                f"Finished with crf {crf}; {metric_name}: "
                f"{get_metric_from_stats(_stats, ctx.vmaf_target_representation)};"
                f" score_error: {score_err}; bitrate: {_stats.bitrate} kb/s"
            )
            ctx.get_kv().set("best_crfs", chunk.chunk_index, crf)
            os.rename(enc.output_path, original_output_path)
            if os.path.exists(probe_file_base):
                shutil.rmtree(probe_file_base)
            return _stats

        metric_name = "vmaf"

        tries = 0
        max_tries = 10

        recent_scores = []

        def run_probe(crf) -> Tuple[float, EncodeStats, float, float, bool]:
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
                metric_to_calculate=Metric.VMAF,
                metric_params=ctx.get_vmaf_options(),
            )
            _metric = get_metric_from_stats(
                stats, statistical_representation=ctx.vmaf_target_representation
            )
            _score = get_weighed_vmaf_score(
                stats,
                codec=enc.get_codec(),
                statistical_representation=ctx.vmaf_target_representation,
                metric_target=metric_target,
            )

            nonlocal tries
            log(
                f"crf: {crf}; {metric_name}: {_metric}; score_error: {_score}; bitrate: {stats.bitrate} kb/s; "
                f"attempt {tries}/{max_tries}"
            )
            trys.append((abs(metric_target - _metric), stats, _metric, _score, crf))

            recent_scores.append(_score)

            # If the list of recent scores is too long, remove the oldest score
            if len(recent_scores) > 4:
                recent_scores.pop(0)

            # Calculate the threshold for the early quit
            threshold = sum(recent_scores) / len(
                recent_scores
            )  # replace this with the desired calculation (e.g., median)

            threshold *= 1.1

            # If the new score is 10% better than the last three ones, quit early
            quit_early = _score < threshold and len(recent_scores) >= 4

            tries += 1
            return abs(metric_target - _metric), stats, _metric, _score, quit_early

        enc.output_path = os.path.join(
            probe_file_base,
            f"{chunk.chunk_index}{enc.get_chunk_file_extension()}",
        )
        enc.passes = 1
        enc.rate_distribution = EncoderRateDistribution.CQ

        best_crf_from_kv = ctx.get_kv().get("best_crfs", chunk.chunk_index)
        if best_crf_from_kv is not None:
            _, stats, _, _, _ = run_probe(best_crf_from_kv)
            return finish(stats, best_crf_from_kv)

        low_crf, high_crf = get_crf_limits(enc, ctx)
        max_score_error = 0.7

        tol = 0.10 if enc.supports_float_crfs() else 1
        gr = (1 + 5**0.5) / 2

        a = high_crf - (high_crf - low_crf) / gr
        b = low_crf + (high_crf - low_crf) / gr

        a = round(a) if not enc.supports_float_crfs() else a
        b = round(b) if not enc.supports_float_crfs() else b

        current_metric_error_a, stats_a, metric_a, score_a, quit_early = run_probe(a)

        if score_a < max_score_error or quit_early:
            return finish(stats_a, a)

        current_metric_error_b, stats_b, metric_b, score_b, quit_early = run_probe(b)

        if score_b < max_score_error or quit_early:
            return finish(stats_b, b)

        while abs(high_crf - low_crf) > tol and tries < max_tries:
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

                (
                    current_metric_error_a,
                    stats_a,
                    metric_a,
                    score_a,
                    quit_early,
                ) = run_probe(a)
                if score_a < max_score_error or quit_early:
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

                (
                    current_metric_error_b,
                    stats_b,
                    metric_b,
                    score_b,
                    quit_early,
                ) = run_probe(b)
                if score_b < max_score_error or quit_early:
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
