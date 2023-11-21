import copy
import json
import os
import time
from abc import abstractmethod, ABC
from typing import List

from tqdm import tqdm

from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.core.timer import Timer
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.parallelEncoding.command import BaseCommandObject
from alabamaEncode.scene.chunk import ChunkObject


class AnalyzeStep(ABC):
    """
    Sets up an Encoder for the final encoding, sometimes does analysis to find the parameters but doesn't have to
    """

    @abstractmethod
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        pass


class FinalEncodeStep(ABC):
    """
    Preforms the final (usually longer) encoding
    """

    @abstractmethod
    def run(self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext) -> EncodeStats:
        pass

    @abstractmethod
    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        pass


class PlainFinalEncode(FinalEncodeStep):
    def run(self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext) -> EncodeStats:
        return enc.run(
            calculate_vmaf=True,
            vmaf_params=VmafOptions(
                uhd=ctx.vmaf_4k_model,
                phone=ctx.vmaf_phone_model,
                ref=ComparisonDisplayResolution.from_string(ctx.vmaf_reference_display)
                if ctx.vmaf_reference_display
                else None,
            ),
        )

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        joined = " && ".join(enc.get_encode_commands())
        return joined


class WeridCapedCrfFinalEncode(FinalEncodeStep):
    def run(self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext) -> EncodeStats:
        stats: EncodeStats = enc.run()

        if stats.bitrate > ctx.cutoff_bitrate:
            tqdm.write(
                chunk.log_prefix()
                + f"at crf {ctx.crf} got {stats.bitrate}, cutoff {ctx.cutoff_bitrate} k/s reached,"
                f" encoding three pass vbr at cutoff "
            )
        else:
            tqdm.write(
                chunk.log_prefix()
                + f"at crf {ctx.crf} got {stats.bitrate}, encoding three pass vbr at {stats.bitrate} k/s "
            )

        encode_bitrate = min(stats.bitrate, ctx.cutoff_bitrate)

        enc.update(
            passes=3,
            rate_distribution=EncoderRateDistribution.VBR,
            bitrate=encode_bitrate,
        )
        enc.svt_bias_pct = 20
        os.remove(enc.output_path)
        stats: EncodeStats = enc.run()
        return stats

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception("dry_run not implemented for WeridCapedCrfFinalEncode")


class CapedCrf(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc.update(
            rate_distribution=EncoderRateDistribution.CQ_VBV,
            bitrate=ctx.max_bitrate,
            crf=ctx.crf,
            passes=1,
        )
        enc.svt_open_gop = True
        return enc


class PlainCrf(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc.update(
            rate_distribution=EncoderRateDistribution.CQ,
            crf=ctx.crf,
            passes=1,
        )
        enc.svt_open_gop = True
        return enc


class PlainVbr(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc.update(
            rate_distribution=EncoderRateDistribution.VBR, bitrate=ctx.bitrate, passes=3
        )
        enc.svt_bias_pct = 20
        return enc


class VbrPerChunkOptimised(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        from alabamaEncode.adaptive.sub.bitrate import get_ideal_bitrate

        enc.update(
            rate_distribution=EncoderRateDistribution.VBR,
            bitrate=get_ideal_bitrate(chunk, ctx),
            passes=3,
        )
        enc.svt_bias_pct = 20
        return enc


class TargetVmaf(AnalyzeStep):
    def __init__(self, alg_type="optuna", probes=8, probe_speed=6):
        self.alg_type = alg_type
        self.probes = probes
        self.probe_speed = probe_speed

    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        original = copy.deepcopy(enc)

        # crfs = [18, 20, 22, 24, 28, 30, 32, 36, 38, 40, 44, 48]
        bad_vmaf_offest = (
            0  # if we target vmaf 95, let's target 94 since the probes are speed 13
        )
        target_vmaf = ctx.vmaf - bad_vmaf_offest
        target_5percentile_vmaf = target_vmaf - bad_vmaf_offest

        class POINT:
            def __init__(self, _crf, vmaf, ssim, bitrate):
                self.crf = _crf
                self.vmaf = vmaf
                self.ssim = ssim
                self.bitrate = bitrate

            vmaf_percentile_1 = 0
            vmaf_percentile_5 = 0
            vmaf_percentile_10 = 0
            vmaf_percentile_25 = 0
            vmaf_percentile_50 = 0
            vmaf_avg = 0

        def log_to_convex_log(_str):
            if ctx.log_level >= 2:
                tqdm.write(_str)
            with open(f"{ctx.temp_folder}/convex.log", "a") as f:
                f.write(_str + "\n")

        # score func, the lowest score gets selected
        def point_to_score(p: POINT):
            """
            calc score including bitrate vmaf and 1% 5% percentiles with weights
            to get the smallest video but with reasonable vmaf and 5% vmaf scores
            """
            score = 0

            model_weights = ctx.crf_model_weights.split(",")
            score_bellow_target_weight = float(model_weights[0])  # 7
            score_above_target_weight = float(model_weights[1])  # 4
            score_bitrate_weight = float(model_weights[2])  # 15
            score_average_weight = float(model_weights[3])  # 2
            score_5_percentile_target_weight = float(model_weights[4])  # 5

            # punish if the score is bellow target
            weight = max(0, target_vmaf - p.vmaf) * score_bellow_target_weight
            score += weight

            # punish if the score is higher then target
            target_weight = max(0, p.vmaf - target_vmaf) * score_above_target_weight
            score += target_weight

            # how 5%tile frames looked compared to overall score
            # punishing if the video is not consistent
            average_weight = abs(p.vmaf_avg - p.vmaf) * score_average_weight
            score += average_weight

            # how 5%tile frames looked compared to target, don't if above target
            # punishing if the worst parts of the video are bellow target
            weight_ = (
                abs(target_vmaf - p.vmaf_percentile_5)
                * score_5_percentile_target_weight
            )
            score += weight_

            # we punish the hardest for bitrate
            bitrate_weight = max(1, (p.bitrate / 100)) * score_bitrate_weight
            score += bitrate_weight  # bitrate

            return score

        enc.update(rate_distribution=EncoderRateDistribution.CQ, passes=1)

        enc.svt_tune = 0

        from alabamaEncode.adaptive.util import get_probe_file_base

        probe_file_base = get_probe_file_base(chunk.chunk_path)

        def crf_to_point(crf_point) -> POINT:
            enc.output_path = os.path.join(
                probe_file_base,
                f"convexhull.{crf_point}{enc.get_chunk_file_extension()}",
            )
            enc.speed = self.probe_speed
            enc.passes = 1
            enc.threads = 1
            enc.grain_synth = 3
            enc.override_flags = None
            enc.crf = crf_point
            probe_vmaf_log = enc.output_path + ".vmaflog"

            stats: EncodeStats = enc.run(
                calculate_vmaf=True,
                vmaf_params=VmafOptions(
                    uhd=ctx.vmaf_4k_model, phone=ctx.vmaf_phone_model
                ),
            )

            point = POINT(crf_point, stats.vmaf, stats.ssim, stats.bitrate)

            point.vmaf_percentile_1 = stats.vmaf_percentile_1
            point.vmaf_percentile_5 = stats.vmaf_percentile_1
            point.vmaf_percentile_10 = stats.vmaf_percentile_10
            point.vmaf_percentile_25 = stats.vmaf_percentile_25
            point.vmaf_percentile_50 = stats.vmaf_percentile_50
            point.vmaf_avg = stats.vmaf_avg

            log_to_convex_log(
                f"{chunk.log_prefix()} crf: {crf_point} vmaf: {stats.vmaf} ssim: {stats.ssim} "
                f"bitrate: {stats.bitrate} 1%: {point.vmaf_percentile_1} 5%: {point.vmaf_percentile_5} "
                f"avg: {point.vmaf_avg} score: {point_to_score(point)}"
            )

            if os.path.exists(probe_vmaf_log):
                os.remove(probe_vmaf_log)
            return point

        def get_score(_crf):
            return point_to_score(crf_to_point(int(_crf)))

        def opt_primitive() -> int:
            crfs = [18, 20, 22, 24, 28, 30, 32, 34, 36, 38, 40, 44, 54]
            points = []

            for _crf in crfs:
                points.append(crf_to_point(_crf))

            closest_score = float("inf")
            _crf = -1

            # PICK LOWEST SCORE
            if len(points) == 1:
                _crf = points[
                    0
                ].crf  # case where there is only one point that is bellow target vmaf
            else:
                for p in points:
                    score = get_score(p)
                    if score < closest_score:
                        _crf = p.crf
                        closest_score = score
            return _crf

        def optimisation_tenary(_get_score, max_probes) -> int:
            def ternary_search(_low, _high, _max_depth, epsilon=1e-9):
                depth = 0

                while _high - _low > epsilon and depth < _max_depth:
                    mid1 = _low + (_high - _low) / 3
                    mid2 = _high - (_high - _low) / 3

                    mid1_score = _get_score(mid1)
                    mid2_score = _get_score(mid2)

                    if mid1_score < mid2_score:
                        _high = mid2
                    else:
                        _low = mid1

                    depth += 1

                return (_low + _high) / 2

            # Set your initial range and maximum depth
            low, high = 0, 63
            max_depth = max_probes / 2
            return int(ternary_search(low, high, max_depth))

        def optimisation_binary(max_probes) -> int:
            low_crf = 10
            high_crf = 55
            epsilon = 0.1

            max_probes -= 1  # since we count from 0

            mid_crf = 0
            depth = 0

            trys = []

            while low_crf <= high_crf and depth < max_probes:
                mid_crf = (low_crf + high_crf) // 2

                # don't try the same crf twice
                if mid_crf in [t[0] for t in trys]:
                    break

                enc.crf = mid_crf
                enc.output_path = os.path.join(
                    probe_file_base,
                    f"convexhull.{mid_crf}{enc.get_chunk_file_extension()}",
                )
                enc.speed = self.probe_speed
                enc.passes = 1
                enc.threads = 1
                enc.grain_synth = 0
                enc.override_flags = None
                stats: EncodeStats = enc.run(
                    calculate_vmaf=True,
                    vmaf_params=VmafOptions(
                        uhd=ctx.vmaf_4k_model,
                        phone=ctx.vmaf_phone_model,
                        ref=ComparisonDisplayResolution.from_string(
                            ctx.vmaf_reference_display
                        )
                        if ctx.vmaf_reference_display
                        else None,
                    ),
                )

                log_to_convex_log(
                    f"{chunk.log_prefix()} crf: {mid_crf} vmaf: {stats.vmaf_result.mean} "
                    f"bitrate: {stats.bitrate} attempt {depth}/{max_probes}"
                )

                if abs(stats.vmaf_result.mean - target_vmaf) <= epsilon:
                    break
                elif stats.vmaf_result.mean > target_vmaf:
                    low_crf = mid_crf + 1
                else:
                    high_crf = mid_crf - 1
                trys.append((mid_crf, stats.vmaf_result.mean))
                depth += 1

            # via linear interpolation, find the crf that is closest to target vmaf
            if len(trys) > 1:
                points = sorted(trys, key=lambda x: abs(x[1] - target_vmaf))
                low_point = points[0]
                high_point = points[1]
                crf_low = low_point[0]
                crf_high = high_point[0]
                vmaf_low = low_point[1]
                vmaf_high = high_point[1]
                interpolated_crf = crf_low + (crf_high - crf_low) * (
                    (target_vmaf - vmaf_low) / (vmaf_high - vmaf_low)
                )

                clamp_low = min(crf_low, crf_high) - 2
                clamp_high = max(crf_low, crf_high) + 2

                # eg. 25-30 are crf points closes to target, so we clamp the interpolated crf to 23-32
                interpolated_crf = max(min(interpolated_crf, clamp_high), clamp_low)

                if enc.supports_float_crfs():
                    mid_crf = interpolated_crf
                else:
                    mid_crf = int(interpolated_crf)

            if mid_crf < low_crf or mid_crf > high_crf:
                # use the most fitting point instead of interpolated
                mid_crf = min(trys, key=lambda x: abs(x[1] - target_vmaf))[0]

            mid_crf = max(min(mid_crf, high_crf), low_crf)  # check

            return mid_crf

        def opt_optuna(_get_score, max_probes) -> int:
            import optuna

            def objective(trial):
                value = trial.suggest_int("value", 0, 63)
                return _get_score(value)

            # quiet logs to 0
            optuna.logging.set_verbosity(0)
            study = optuna.create_study(direction="minimize")
            study.optimize(objective, n_trials=max_probes)
            result = study.best_params["value"]

            return int(result)

        def opt_optuna_modelless(_crf_to_point, max_probes) -> int:
            import optuna

            def objective(trial):
                crf_trial = trial.suggest_int("crf", 15, 63)
                point = _crf_to_point(crf_trial)

                diff_vmaf = abs(target_vmaf - point.vmaf)
                percentile_diff = abs(target_5percentile_vmaf - point.vmaf_percentile_5)
                bitrate = point.bitrate / 1000
                # divide by 1000 to 1000kb/s -> 1
                # since optuna will prioritize lower bitrate if it's in the 1000s
                return (
                    diff_vmaf,
                    percentile_diff,
                    bitrate,
                )

            # optuna.logging.set_verbosity(0)
            study = optuna.create_study(directions=["minimize", "minimize", "minimize"])

            study.optimize(objective, n_trials=max_probes)

            return study.best_trials[0].params["crf"]

        match self.alg_type:
            case "optuna":
                crf = opt_optuna(get_score, self.probes)
            case "modelless":
                crf = opt_optuna_modelless(crf_to_point, self.probes)
            case "primitive":
                crf = opt_primitive()
            case "ternary":
                crf = optimisation_tenary(get_score, self.probes)
            case "binary":
                crf = optimisation_binary(self.probes)
            case _:
                raise Exception(f"Unknown alg_type {self.alg_type}")

        log_to_convex_log(f"{chunk.log_prefix()}Convexhull crf: {crf}")
        enc.update(
            passes=1,
            rate_distribution=EncoderRateDistribution.CQ,
            output_path=chunk.chunk_path,
        )
        enc.crf = crf

        enc.svt_tune = 0
        enc.svt_overlay = 0
        enc.override_flags = ctx.override_flags
        enc.speed = original.speed
        enc.grain_synth = original.grain_synth

        return enc


class GrainSynth(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        from alabamaEncode.adaptive.sub.grain2 import calc_grainsynth_of_scene

        from alabamaEncode.adaptive.util import get_probe_file_base

        probe_file_base = get_probe_file_base(chunk.chunk_path)
        grain_synth_result = calc_grainsynth_of_scene(
            chunk, probe_file_base, scale_vf=ctx.scale_string, crop_vf=ctx.crop_string
        )
        grain_synth_result = min(grain_synth_result, 18)
        enc.grain_synth = grain_synth_result

        grain_log = f"{ctx.temp_folder}grain.log"
        with open(grain_log, "a") as f:
            f.write(f"{chunk.log_prefix()}computed gs {enc.grain_synth}\n")
        return enc


class BaseAnalyzer(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        enc = ctx.get_encoder()
        enc.setup(chunk=chunk, config=ctx)
        enc.update(
            grain_synth=ctx.grain_synth,
            speed=ctx.speed,
            rate_distribution=EncoderRateDistribution.CQ,
            crf=ctx.crf,
            passes=1,
        )
        enc.qm_enabled = True
        enc.qm_max = 8
        enc.qm_min = 0
        return enc


def analyzer_factory(ctx: AlabamaContext) -> List[AnalyzeStep]:
    steps = [BaseAnalyzer()]

    if ctx.flag1 is True:
        steps.append(PlainCrf())
    elif ctx.crf_based_vmaf_targeting is True:
        steps.append(
            TargetVmaf(
                alg_type=ctx.vmaf_targeting_model,
                probes=ctx.vmaf_probe_count,
                probe_speed=ctx.probe_speed_override,
            )
        )
    else:
        if ctx.crf_bitrate_mode:
            steps.append(CapedCrf())
        elif ctx.crf != -1:
            steps.append(PlainCrf())
        else:
            if ctx.bitrate_adjust_mode == "chunk":
                steps.append(VbrPerChunkOptimised())
            else:
                steps.append(PlainVbr())

    if ctx.grain_synth == -2:
        steps.append(GrainSynth())

    if len(steps) == 0:
        raise Exception("Failed to Create the analyze steps in analyzer_factory")
    return steps


def finalencode_factory(ctx: AlabamaContext) -> FinalEncodeStep:
    if ctx.flag1:
        final_step = WeridCapedCrfFinalEncode()
    else:
        final_step = PlainFinalEncode()
    if final_step is None:
        raise Exception("final_step is None, LOGIC BUG")
    return final_step


class AdaptiveCommand(BaseCommandObject):
    """
    Class that gets the ideal bitrate and encodes the final chunk
    """

    ctx: AlabamaContext
    chunk: ChunkObject

    def __init__(self, ctx: AlabamaContext, chunk: ChunkObject):
        super().__init__()
        self.ctx = ctx
        self.chunk = chunk

    # how long (seconds) before we time out the final encoding
    # currently set to 30 minutes
    final_encode_timeout = 1800

    run_on_celery = False

    def run(self):
        total_start = time.time()

        analyze_steps: List[AnalyzeStep] = analyzer_factory(self.ctx)

        # using it with a statement with MessageWriter
        timeing = Timer()

        timeing.start("analyze_step")

        enc = None
        for step in analyze_steps:
            timeing.start(f"analyze_step_{step.__class__.__name__}")
            enc = step.run(self.ctx, self.chunk, enc)
            timeing.stop(f"analyze_step_{step.__class__.__name__}")

        rate_search_time = timeing.stop("analyze_step")

        enc.running_on_celery = self.run_on_celery

        final_step: FinalEncodeStep = finalencode_factory(self.ctx)

        if self.ctx.dry_run:
            print(f"dry run chunk: {self.chunk.chunk_index}")
            s = final_step.dry_run(enc, self.chunk)
            print(s)
            return

        timeing.start("final_step")

        final_stats = None
        try:
            final_stats = final_step.run(enc, chunk=self.chunk, ctx=self.ctx)
        except Exception as e:
            print(f"[{self.chunk.chunk_index}] error while encoding: {e}")

        timeing.stop("final_step")
        timeing.finish()

        # round to two places
        total_fps = round(self.chunk.get_frame_count() / (time.time() - total_start), 2)
        # target bitrate vs actual bitrate difference in %
        target_miss_proc = (final_stats.bitrate - enc.bitrate) / enc.bitrate * 100
        final_stats.total_fps = total_fps
        final_stats.target_miss_proc = target_miss_proc
        final_stats.chunk_index = self.chunk.chunk_index
        final_stats.rate_search_time = rate_search_time
        self.ctx.log(
            f"[{self.chunk.chunk_index}] final stats:"
            f" vmaf={final_stats.vmaf} "
            f" time={int(final_stats.time_encoding)}s "
            f" bitrate={final_stats.bitrate}k"
            f" bitrate_target_miss={target_miss_proc:.2f}%"
            f" chunk_length={round(self.chunk.get_lenght(), 2)}s"
            f" total_fps={total_fps}"
        )
        # save the stats to [temp_folder]/chunks.log
        with open(f"{self.ctx.temp_folder}/chunks.log", "a") as f:
            f.write(json.dumps(final_stats.get_dict()) + "\n")
