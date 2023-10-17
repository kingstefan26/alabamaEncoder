import os
import time

from tqdm import tqdm

from alabamaEncode.adaptive.sub.bitrate import get_ideal_bitrate
from alabamaEncode.adaptive.util import get_probe_file_base
from alabamaEncode.encoders.RateDiss import RateDistribution
from alabamaEncode.encoders.encodeStats import EncodeStats
from alabamaEncode.encoders.encoder.AbstractEncoder import AbstractEncoder
from alabamaEncode.encoders.encoder.impl.Svtenc import AbstractEncoderSvtenc
from alabamaEncode.parallelEncoding.Command import CommandObject


class AdaptiveCommand(CommandObject):
    """
    Class that gets the ideal bitrate and encodes the final chunk
    """

    def __init__(self):
        super().__init__()

    # how long (seconds) before we time out the final encoding
    # currently set to 30 minutes
    final_encode_timeout = 1800

    run_on_celery = False

    def run(self):
        total_start = time.time()

        enc: AbstractEncoder = self.config.get_encoder()

        enc.running_on_celery = self.run_on_celery
        enc.setup(chunk=self.chunk, config=self.config)
        enc.update(grain_synth=self.config.grain_synth, speed=self.config.speed)
        rate_search_time = time.time()
        if self.config.flag1:
            enc.update(
                passes=1, rate_distribution=RateDistribution.CQ, crf=self.config.crf
            )
            enc.svt_open_gop = True

            stats: EncodeStats = enc.run(timeout_value=self.final_encode_timeout)

            if stats.bitrate > self.config.cutoff_bitrate:
                tqdm.write(
                    self.chunk.log_prefix()
                    + f"at crf {self.config.crf} got {stats.bitrate}, cutoff {self.config.cutoff_bitrate} k/s reached, encoding three pass vbr at cutoff "
                )
            else:
                tqdm.write(
                    self.chunk.log_prefix()
                    + f"at crf {self.config.crf} got {stats.bitrate}, encoding three pass vbr at {stats.bitrate} k/s "
                )

            encode_bitrate = min(stats.bitrate, self.config.cutoff_bitrate)

            enc.update(
                passes=3,
                rate_distribution=RateDistribution.VBR,
                bitrate=encode_bitrate,
            )
            enc.svt_bias_pct = 20
            os.remove(enc.output_path)
            stats: EncodeStats = enc.run(timeout_value=self.final_encode_timeout)

            # round to two places
            self.calc_stats(enc, stats, total_start)
            return
        elif self.config.flag2 is True:
            # crfs = [18, 20, 22, 24, 28, 30, 32, 36, 38, 40, 44, 48]
            crfs = [18, 20, 22, 24, 28, 30, 32, 36, 38, 40]
            points = []
            target_vmaf = self.config.vmaf

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

            enc.qm_enabled = True
            enc.qm_max = 8
            enc.qm_min = 0
            enc.svt_open_gop = True

            def log_to_convex_log(str):
                with open(f"{self.config.temp_folder}/convex.log", "a") as f:
                    f.write(str + "\n")

            def get_score(p: POINT):
                """
                calc score including bitrate vmaf and 1% 5% percentiles with weights
                to get the smallest video but with reasonable vmaf and 5% vmaf scores
                """
                score = 0

                score_bellow_target_weight = 7
                score_above_target_weight = 3
                score_bitrate_weight = 19
                score_average_weight = 2
                score_5_percentile_target_weight = 15

                # punish if the score is bellow target
                score += max(0, target_vmaf - p.vmaf) * score_bellow_target_weight

                # punish if the score is higher then target
                score += max(0, p.vmaf - target_vmaf) * score_above_target_weight

                # how 5%tile frames looked compared to overall score
                # punishing if the video is not consistent
                score += abs(p.vmaf_avg - p.vmaf) * score_average_weight

                # how 5%tile frames looked compared to target, don't if above target
                # punishing if the worst parts of the video are bellow target
                score += (
                    max(0, target_vmaf - p.vmaf_percentile_5)
                    * score_5_percentile_target_weight
                )

                # we punish the hardest for bitrate
                score += (p.bitrate / 1000) * score_bitrate_weight  # bitrate
                return score

            enc.update(rate_distribution=RateDistribution.CQ)

            if enc is AbstractEncoderSvtenc:
                enc.svt_tune = 1

            probe_file_base = get_probe_file_base(
                self.chunk.chunk_path, self.config.temp_folder
            )
            for crf in crfs:

                enc.update(
                    output_path=(
                        probe_file_base
                        + f"convexhull.{crf}{enc.get_chunk_file_extension()}"
                    ),
                    speed=12,
                    passes=1,
                    grain_synth=-1,
                )
                enc.crf = crf
                stats: EncodeStats = enc.run(
                    timeout_value=self.final_encode_timeout,
                    calculate_vmaf=True,
                    vmaf_params={
                        "uhd_model": True,
                        "disable_enchancment_gain": False
                    },
                )

                point = POINT(crf, stats.vmaf, stats.ssim, stats.bitrate)

                point.vmaf_percentile_1 = stats.vmaf_percentile_1
                point.vmaf_percentile_5 = stats.vmaf_percentile_1
                point.vmaf_percentile_10 = stats.vmaf_percentile_10
                point.vmaf_percentile_25 = stats.vmaf_percentile_25
                point.vmaf_percentile_50 = stats.vmaf_percentile_50
                point.vmaf_avg = stats.vmaf_avg

                log_to_convex_log(
                    f"{self.chunk.log_prefix()} crf: {crf} vmaf: {stats.vmaf} ssim: {stats.ssim} bitrate: {stats.bitrate} 1%: {point.vmaf_percentile_1} 5%: {point.vmaf_percentile_5} avg: {point.vmaf_avg} score: {get_score(point)}"
                )

                points.append(point)

            if enc is AbstractEncoderSvtenc:
                enc.svt_tune = 0

            # convex hull

            closest_score = float("inf")
            crf = -1

            ## PICK CLOSEST TO TARGET QUALITY
            # pick the crf from point closest to target_vmaf
            # for p in points:
            #     if abs(target_vmaf - closest_score) > abs(target_vmaf - p.vmaf):
            #         crf = p.crf
            #         closest_score = p.vmaf

            ## PICK LOWEST BITRATE WITH QUALITY ABOVE TARGET
            # pick the crf from point with lowest bitrate with vmaf above target_vmaf
            # if len(points) == 1:
            #     crf = points[
            #         0
            #     ].crf  # case where there is only one point that is bellow target vmaf
            # else:
            #     for p in points:
            #         if p.vmaf >= target_vmaf and p.bitrate < closest_score:
            #             crf = p.crf
            #             closest_score = p.bitrate

            ## PICK LOWEST SCORE
            if len(points) == 1:
                crf = points[
                    0
                ].crf  # case where there is only one point that is bellow target vmaf
            else:
                for p in points:
                    score = get_score(p)
                    if score < closest_score:
                        crf = p.crf
                        closest_score = score

            log_to_convex_log(f"{self.chunk.log_prefix()}Convexhull crf: {crf}")
            enc.update(
                passes=1,
                grain_synth=self.config.grain_synth,
                speed=self.config.speed,
                rate_distribution=RateDistribution.CQ,
                output_path=self.chunk.chunk_path,
                crf=crf,
            )

            enc.svt_supperres_mode = 4

            if self.config.dry_run:
                for comm in enc.get_encode_commands():
                    print(comm)

            try:
                stats: EncodeStats = enc.run(timeout_value=self.final_encode_timeout)
                self.calc_stats(enc, stats, total_start)
            except Exception as e:
                print(f"[{self.chunk.chunk_index}] error while encoding: {e}")
            return

        else:
            if self.config.crf_bitrate_mode:
                enc.update(
                    passes=1,
                    bitrate=self.config.bitrate,
                    rate_distribution=RateDistribution.CQ_VBV,
                    crf=self.config.crf,
                )
                enc.svt_open_gop = True
                enc.max_bitrate = self.config.max_bitrate
            elif self.config.crf != -1:
                enc.update(
                    passes=1,
                    rate_distribution=RateDistribution.CQ,
                    crf=self.config.crf,
                )
                enc.qm_max = 8
                enc.qm_enabled = True
                enc.qm_min = 0
                enc.svt_open_gop = True
            else:
                if self.config.bitrate_adjust_mode == "chunk":
                    self.chunk.ideal_bitrate = get_ideal_bitrate(
                        self.chunk, self.config
                    )
                else:
                    self.chunk.ideal_bitrate = self.config.bitrate

                enc.update(
                    passes=3,
                    rate_distribution=RateDistribution.VBR,
                    bitrate=self.chunk.ideal_bitrate,
                )
                enc.svt_bias_pct = 20

        rate_search_time = time.time() - rate_search_time

        try:
            if self.config.dry_run:
                print(f"dry run chunk: {self.chunk.chunk_index}")
                for comm in enc.get_encode_commands():
                    print(comm)
                return
            stats: EncodeStats = enc.run(
                timeout_value=self.final_encode_timeout,
            )
            stats.rate_search_time = rate_search_time

            self.calc_stats(enc, stats, total_start)
        except Exception as e:
            print(f"[{self.chunk.chunk_index}] error while encoding: {e}")

    def calc_stats(self, enc, stats, total_start):
        # round to two places
        total_fps = round(self.chunk.get_frame_count() / (time.time() - total_start), 2)
        # target bitrate vs actual bitrate diffrence in %
        taget_miss_proc = (stats.bitrate - enc.bitrate) / enc.bitrate * 100
        stats.total_fps = total_fps
        stats.target_miss_proc = taget_miss_proc
        stats.chunk_index = self.chunk.chunk_index
        self.config.log(
            f"[{self.chunk.chunk_index}] final stats:"
            f" vmaf={stats.vmaf} "
            f" time={int(stats.time_encoding)}s "
            f" bitrate={stats.bitrate}k"
            f" bitrate_target_miss={taget_miss_proc:.2f}%"
            f" chunk_lenght={round(self.chunk.get_lenght(), 2)}s"
            f" total_fps={total_fps}"
        )
        # save the stats to [temp_folder]/stats/chunk_[index].json
        os.makedirs(f"{self.config.temp_folder}/stats", exist_ok=True)
        stats.save(
            f"{self.config.temp_folder}/stats/chunk_{self.chunk.chunk_index}.json"
        )
