import json
import os
import time
from abc import abstractmethod, ABC

from tqdm import tqdm

from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.encoders.encoder.encoder import AbstractEncoder
from alabamaEncode.encoders.encoderMisc import EncodeStats, EncoderRateDistribution
from alabamaEncode.parallelEncoding.command import BaseCommandObject
from alabamaEncode.scene.chunk import ChunkObject


class AnalyzeStep(ABC):
    """
    Sets up an AbstactEncoder for the final encoding, sometimes does analysis to find the parameters but doesnt have to
    """

    @abstractmethod
    def run(self, ctx: AlabamaContext, chunk: ChunkObject) -> AbstractEncoder:
        pass


class FinalEncodeStep(ABC):
    """
    Preforms the final (usually longer) encoding
    """

    @abstractmethod
    def run(
        self, enc: AbstractEncoder, chunk: ChunkObject, ctx: AlabamaContext
    ) -> EncodeStats:
        pass

    @abstractmethod
    def dry_run(self, enc: AbstractEncoder, chunk: ChunkObject) -> str:
        pass


class PlainFinalEncode(FinalEncodeStep):
    def run(
        self, enc: AbstractEncoder, chunk: ChunkObject, ctx: AlabamaContext
    ) -> EncodeStats:
        return enc.run()

    def dry_run(self, enc: AbstractEncoder, chunk: ChunkObject) -> str:
        joined = " && ".join(enc.get_encode_commands())
        return joined


class WeridCapedCrfFinalEncode(FinalEncodeStep):
    def run(
        self, enc: AbstractEncoder, chunk: ChunkObject, ctx: AlabamaContext
    ) -> EncodeStats:
        stats: EncodeStats = enc.run()

        if stats.bitrate > ctx.cutoff_bitrate:
            tqdm.write(
                chunk.log_prefix()
                + f"at crf {ctx.crf} got {stats.bitrate}, cutoff {ctx.cutoff_bitrate} k/s reached, encoding three pass vbr at cutoff "
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

    def dry_run(self, enc: AbstractEncoder, chunk: ChunkObject) -> str:
        raise Exception("dry_run not implemented for WeridCapedCrfFinalEncode")


class CapedCrf(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject) -> AbstractEncoder:
        enc: AbstractEncoder = ctx.get_encoder()
        enc.setup(chunk=chunk, config=ctx)
        enc.update(
            grain_synth=ctx.grain_synth,
            speed=ctx.speed,
            rate_distribution=EncoderRateDistribution.CQ_VBV,
            bitrate=ctx.max_bitrate,
            crf=ctx.crf,
            passes=1,
        )
        enc.svt_open_gop = True
        enc.qm_enabled = True
        enc.qm_max = 8
        enc.qm_min = 0
        return enc


class PlainCrf(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject) -> AbstractEncoder:
        enc: AbstractEncoder = ctx.get_encoder()
        enc.setup(chunk=chunk, config=ctx)
        enc.update(
            grain_synth=ctx.grain_synth,
            speed=ctx.speed,
            rate_distribution=EncoderRateDistribution.CQ,
            crf=ctx.crf,
            passes=1,
        )
        enc.svt_open_gop = True
        enc.qm_enabled = True
        enc.qm_max = 8
        enc.qm_min = 0
        return enc


class PlainVbr(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject) -> AbstractEncoder:
        enc: AbstractEncoder = ctx.get_encoder()
        enc.setup(chunk=chunk, config=ctx)
        enc.update(
            grain_synth=ctx.grain_synth,
            speed=ctx.speed,
            rate_distribution=EncoderRateDistribution.VBR,
            bitrate=ctx.bitrate,
            passes=3,
        )
        enc.qm_enabled = True
        enc.qm_max = 8
        enc.qm_min = 0
        enc.svt_bias_pct = 20
        return enc


class VbrPerChunkOptimised(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject) -> AbstractEncoder:
        enc: AbstractEncoder = ctx.get_encoder()
        enc.setup(chunk=chunk, config=ctx)
        from alabamaEncode.adaptive.sub.bitrate import get_ideal_bitrate

        enc.update(
            grain_synth=ctx.grain_synth,
            speed=ctx.speed,
            rate_distribution=EncoderRateDistribution.VBR,
            bitrate=get_ideal_bitrate(chunk, ctx),
            passes=3,
        )
        enc.qm_enabled = True
        enc.qm_max = 8
        enc.qm_min = 0
        enc.svt_bias_pct = 20
        return enc


class TargetVmaf(AnalyzeStep):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject) -> AbstractEncoder:
        enc: AbstractEncoder = ctx.get_encoder()
        enc.setup(chunk=chunk, config=ctx)
        enc.update(
            grain_synth=ctx.grain_synth,
            speed=ctx.speed,
            rate_distribution=EncoderRateDistribution.CQ,
            crf=ctx.crf,
            passes=1,
        )
        enc.svt_open_gop = True
        enc.qm_enabled = True
        enc.qm_max = 8
        enc.qm_min = 0
        # crfs = [18, 20, 22, 24, 28, 30, 32, 36, 38, 40, 44, 48]
        bad_vmaf_offest = (
            1  # if we target vmaf 95, lets target 94 since the probes are speed 13
        )
        target_vmaf = ctx.vmaf - bad_vmaf_offest

        class POINT:
            def __init__(self, crf, vmaf, ssim, bitrate):
                self.crf = crf
                self.vmaf = vmaf
                self.ssim = ssim
                self.bitrate = bitrate

            vmaf_percentile_1 = 0
            vmaf_percentile_5 = 0
            vmaf_percentile_10 = 0
            vmaf_percentile_25 = 0
            vmaf_percentile_50 = 0
            vmaf_avg = 0

        def log_to_convex_log(str):
            with open(f"{ctx.temp_folder}/convex.log", "a") as f:
                f.write(str + "\n")

        # score func, the lowest score gets selected
        def get_score(p: POINT):
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
                max(0, target_vmaf - p.vmaf_percentile_5)
                * score_5_percentile_target_weight
            )
            score += weight_

            # we punish the hardest for bitrate
            bitrate_weight = max(1, (p.bitrate / 100)) * score_bitrate_weight
            score += bitrate_weight  # bitrate

            return score

        enc.update(rate_distribution=EncoderRateDistribution.CQ)

        enc.svt_tune = 0

        from alabamaEncode.adaptive.util import get_probe_file_base

        probe_file_base = get_probe_file_base(chunk.chunk_path, ctx.temp_folder)

        def crf_to_point(crf_point) -> POINT:
            enc.update(
                output_path=(
                    probe_file_base
                    + f"convexhull.{crf_point}{enc.get_chunk_file_extension()}"
                ),
                speed=12,
                passes=1,
                grain_synth=-1,
            )
            enc.crf = crf_point
            probe_vmaf_log = enc.output_path + ".vmaflog"

            stats: EncodeStats = enc.run(
                calculate_vmaf=True,
                vmaf_params={
                    "log_path": probe_vmaf_log,
                    "disable_enchancment_gain": False,
                    "uhd_model": ctx.vmaf_4k_model,
                    "phone_model": ctx.vmaf_phone_model,
                },
            )

            point = POINT(crf_point, stats.vmaf, stats.ssim, stats.bitrate)

            point.vmaf_percentile_1 = stats.vmaf_percentile_1
            point.vmaf_percentile_5 = stats.vmaf_percentile_1
            point.vmaf_percentile_10 = stats.vmaf_percentile_10
            point.vmaf_percentile_25 = stats.vmaf_percentile_25
            point.vmaf_percentile_50 = stats.vmaf_percentile_50
            point.vmaf_avg = stats.vmaf_avg

            log_to_convex_log(
                f"{chunk.log_prefix()} crf: {crf_point} vmaf: {stats.vmaf} ssim: {stats.ssim} bitrate: {stats.bitrate} 1%: {point.vmaf_percentile_1} 5%: {point.vmaf_percentile_5} avg: {point.vmaf_avg} score: {get_score(point)}"
            )

            if os.path.exists(probe_vmaf_log):
                os.remove(probe_vmaf_log)
            return point

        # crfs = [18, 20, 22, 24, 28, 30, 32, 34, 36, 38, 40, 44, 54]
        # points = []
        #
        # for crf in crfs:
        #     point = crf_to_point(crf)
        #     points.append(point)
        #
        # closest_score = float("inf")
        # crf = -1
        #
        # ## PICK LOWEST SCORE
        # if len(points) == 1:
        #     crf = points[
        #         0
        #     ].crf  # case where there is only one point that is bellow target vmaf
        # else:
        #     for p in points:
        #         score = get_score(p)
        #         if score < closest_score:
        #             crf = p.crf
        #             closest_score = score

        def ternary_search(low, high, max_depth, epsilon=1e-9):
            depth = 0

            while high - low > epsilon and depth < max_depth:
                mid1 = low + (high - low) / 3
                mid2 = high - (high - low) / 3

                mid1_score = get_score(crf_to_point(int(mid1)))
                mid2_score = get_score(crf_to_point(int(mid2)))

                if mid1_score < mid2_score:
                    high = mid2
                else:
                    low = mid1

                depth += 1

            return (low + high) / 2

        # Set your initial range and maximum depth
        low, high = 0, 63
        max_depth = 4
        crf = int(ternary_search(low, high, max_depth))

        # print(f"{chunk.log_prefix()}Convexhull crf: {crf}")
        log_to_convex_log(f"{chunk.log_prefix()}Convexhull crf: {crf}")
        enc.update(
            passes=1,
            grain_synth=ctx.grain_synth,
            speed=ctx.speed,
            rate_distribution=EncoderRateDistribution.CQ,
            output_path=chunk.chunk_path,
            crf=crf,
        )

        enc.svt_tune = 0
        enc.svt_overlay = 0

        return enc


def analyzer_factory(ctx: AlabamaContext) -> AnalyzeStep:
    analyze_step = None
    if ctx.flag1 is True:
        analyze_step = PlainCrf()
    elif ctx.crf_based_vmaf_targeting is True:
        analyze_step = TargetVmaf()
    else:
        if ctx.crf_bitrate_mode:
            analyze_step = CapedCrf()
        elif ctx.crf != -1:
            analyze_step = PlainCrf()
        else:
            if ctx.bitrate_adjust_mode == "chunk":
                analyze_step = VbrPerChunkOptimised()
            else:
                analyze_step = PlainVbr()
    if analyze_step is None:
        raise Exception("Failed to Create the analyze step in analyzer_factory")
    return analyze_step


def finalencode_factory(ctx: AlabamaContext) -> FinalEncodeStep:
    final_step = None
    if ctx.flag1:
        final_step = WeridCapedCrfFinalEncode()
    else:
        final_step = PlainFinalEncode()
    if final_step is None:
        raise Exception("final_step is None, LOGIC BUG")
    return final_step


class Timer:
    def __init__(self):
        self.timers = {}

    def start(self, name: str):
        self.timers[name] = time.time()

    def stop(self, name: str):
        if name not in self.timers:
            raise Exception("Timer not started")
        self.timers[name] = time.time() - self.timers[name]
        return self.timers[name]

    def finish(self, loud=False):
        if loud:
            print("timers:")
            for key in self.timers:
                print(f"{key}: {self.timers[key]}s")
        return self.timers


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

        analyze_step: AnalyzeStep = analyzer_factory(self.ctx)

        # using with statement with MessageWriter
        timeing = Timer()

        timeing.start("analyze_step")
        enc = analyze_step.run(self.ctx, self.chunk)
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

        final_step = timeing.stop("final_step")
        timeing.finish()

        # round to two places
        total_fps = round(self.chunk.get_frame_count() / (time.time() - total_start), 2)
        # target bitrate vs actual bitrate diffrence in %
        taget_miss_proc = (final_stats.bitrate - enc.bitrate) / enc.bitrate * 100
        final_stats.total_fps = total_fps
        final_stats.target_miss_proc = taget_miss_proc
        final_stats.chunk_index = self.chunk.chunk_index
        final_stats.rate_search_time = rate_search_time
        self.ctx.log(
            f"[{self.chunk.chunk_index}] final stats:"
            f" vmaf={final_stats.vmaf} "
            f" time={int(final_stats.time_encoding)}s "
            f" bitrate={final_stats.bitrate}k"
            f" bitrate_target_miss={taget_miss_proc:.2f}%"
            f" chunk_lenght={round(self.chunk.get_lenght(), 2)}s"
            f" total_fps={total_fps}"
        )
        # save the stats to [temp_folder]/chunks.log
        try:
            with open(f"{self.ctx.temp_folder}/chunks.log", "a") as f:
                f.write(json.dumps(final_stats.get_dict()) + "\n")
        except:
            pass
