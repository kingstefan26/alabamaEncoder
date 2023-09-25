import os
import time

from tqdm import tqdm

from alabamaEncode.adaptiveEncoding.sub.bitrate import get_ideal_bitrate
from alabamaEncode.adaptiveEncoding.util import get_probe_file_base
from alabamaEncode.encoders.RateDiss import RateDistribution
from alabamaEncode.encoders.encodeStats import EncodeStats
from alabamaEncode.parallelEncoding.Command import CommandObject


class AdaptiveCommand(CommandObject):
    """
    Class that gets the ideal bitrate and encodes the final chunk
    """

    def __init__(self):
        super().__init__()

    # how long (seconds) before we time out the final encoding
    # currently set to 10 minutes
    final_encode_timeout = 1000

    run_on_celery = False

    def run(self):
        total_start = time.time()

        enc = self.config.get_encoder()

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
            crfs = [18, 20, 22, 24, 28, 30, 32, 36, 38, 40, 44, 48]
            points = []

            class POINT:
                def __init__(self, crf, vmaf, ssim, bitrate):
                    self.crf = crf
                    self.vmaf = vmaf
                    self.ssim = ssim
                    self.bitrate = bitrate

            enc.qm_enabled = True
            enc.qm_max = 15
            enc.qm_min = 8
            enc.svt_open_gop = True

            enc.update(rate_distribution=RateDistribution.CQ)

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
                    calcualte_ssim=True,
                )

                points.append(POINT(crf, stats.vmaf, stats.ssim, stats.bitrate))

            # convex hull
            target_vmaf = self.config.vmaf
            closest_vmaf = float("inf")
            crf = -1
            # pick the crf from point closest to target_vmaf
            for p in points:
                if abs(target_vmaf - closest_vmaf) > abs(target_vmaf - p.vmaf):
                    crf = p.crf
                    closest_vmaf = p.vmaf

            tqdm.write(f"{self.chunk.log_prefix()}Convexhull crf: {crf}")
            enc.update(
                passes=1,
                grain_synth=self.config.grain_synth,
                speed=self.config.speed,
                rate_distribution=RateDistribution.CQ,
                output_path=self.chunk.chunk_path,
                crf=crf,
            )

            stats: EncodeStats = enc.run(timeout_value=self.final_encode_timeout)
            self.calc_stats(enc, stats, total_start)
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
