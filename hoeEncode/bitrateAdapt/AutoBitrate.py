import copy
import logging
import os
import pickle
import shutil
import time

from hoeEncode.bitrateAdapt.AutoGrain import AutoGrain
from hoeEncode.encoders.EncoderStats import EncodingStatsObject
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Aomenc import AbstractEncoderAomEnc
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import get_video_ssim, get_total_bitrate, get_video_vmeth, sizeof_fmt
from hoeEncode.parallelEncoding.Command import CommandObject


class ConvexEncoder(CommandObject):

    def __init__(self):
        super().__init__()
        self.stats = EncodingStatsObject()

    # what speed do we run while searching bitrate
    convex_speed = 8

    # speed for the final encode
    encode_speed = 3

    remove_probes = True  # after encoding is done remove the probes

    threads = 1

    # how long (seconds) before we time out the final encode
    # currently set to ~30 minutes
    final_encode_timeout = 1600

    flag_7 = True  # for low bitrates always use at least 1 grain

    flag_11 = False  # calculate the ideal grain regardless of config object, can yield -10% size gains

    flag_15 = False  # use aomenc

    bias_pct = 93  # how much we want to cbr the final encode

    complexity_clamp_down = 0.8
    complexity_clamp_up = 0.35
    clamp_complexity = True

    db_target = 20

    # very much hd 22
    # recomended 21
    # csual 19
    # ok 18

    def complexity_rate_estimation(self, ignore_cache=False):
        probe_file_base = self.get_probe_name()
        cache_filename = f'{probe_file_base}.complexity.speed{self.convex_speed}.pt'

        # check if we have already done this
        if os.path.exists(cache_filename) and ignore_cache is False:
            return pickle.load(open(cache_filename, 'rb'))

        test_probe_path = f'{probe_file_base}complexity.probe.ivf'

        if self.flag_15 is True:
            enc = AbstractEncoderAomEnc()
        else:
            enc = AbstractEncoderSvtenc()

        enc.update(speed=self.convex_speed,
                   passes=1,
                   temp_folder=self.config.temp_folder,
                   chunk=self.job.chunk,
                   svt_grain_synth=0,
                   current_scene_index=self.job.current_scene_index,
                   output_path=test_probe_path,
                   threads=1)

        enc.update(bitrate=self.config.bitrate, rate_distribution=RateDistribution.VBR)

        enc.run(override_if_exists=False)

        (ssim, ssim_db) = get_video_ssim(test_probe_path, self.job.chunk, get_db=True)

        # Calculate the ratio between the target ssim dB and the current ssim dB
        ratio = 10 ** ((self.db_target - ssim_db) / 10)

        # Clamp the ratio to the complexity clamp
        if self.clamp_complexity:
            ratio = max(min(ratio, 1 + self.complexity_clamp_up), 1 - self.complexity_clamp_down)

        # Interpolate the ideal encode rate using the ratio
        ideal_rate = self.config.bitrate * ratio
        ideal_rate = int(ideal_rate)

        print(
            f'{self.log_prefix()}===============\n'
            f'{self.log_prefix()} encode rate: {self.config.bitrate}k/s\n'
            f'{self.log_prefix()} ssim dB when using target bitrate: {ssim_db} (wanted: {self.db_target})\n'
            f'{self.log_prefix()} ratio = 10 ** (dB_target - dB) / 10 = {ratio}\n'
            f'{self.log_prefix()} ideal rate: max(min(encode_rate * ratio, upper_clamp), bottom_clamp) = {ideal_rate:.2f}k/s\n'
            f'{self.log_prefix()}==============='
        )

        # if self.remove_probes:
        #     os.remove(test_probe_path)

        pickle.dump(ideal_rate, open(cache_filename, 'wb'))
        return ideal_rate

    def get_probe_file_base(self, encoded_scene_path) -> str:
        """
        This filename will be used to craete grain/rate probes
        eg:
        if filename is "./test/1.ivf"
        then ill create
        "./test/1_rate_probes/probe.bitrate.speed12.grain0.ivf"
        "./test/1_rate_probes/probe.bitrate.speed12.grain1.ivf"
        "./test/1_rate_probes/probe.grain0.speed12.avif"
        etc
        """
        encoded_scene_path = copy.deepcopy(encoded_scene_path)
        path_without_file = os.path.dirname(encoded_scene_path)
        filename = os.path.basename(encoded_scene_path)
        filename_without_ext = os.path.splitext(filename)[0]
        # new folder for the rate probes
        probe_folder_path = os.path.join(self.config.temp_folder, path_without_file,
                                         filename_without_ext + '_rate_probes')
        # make the folder
        os.makedirs(probe_folder_path, exist_ok=True)
        # new file base
        return os.path.join(probe_folder_path, filename_without_ext)

    def get_probe_name(self):
        return self.get_probe_file_base(self.job.encoded_scene_path)

    def get_ideal_grain_bitrate(self):

        if self.flag_11 is False:
            if self.config.grain_synth is None or self.config.grain_synth == -1:
                raise Exception('grain_synth is None or -1')
            ideal_grain = self.config.grain_synth
        else:
            auto_grain = AutoGrain(chunk=self.job.chunk,
                                   test_file_path=self.get_probe_file_base(self.job.encoded_scene_path))

            ideal_grain = auto_grain.get_ideal_grain_butteraugli()
            logging.debug('ideal grain (butteraugli method): ' + str(ideal_grain))

        if self.flag_7 is True:
            if ideal_grain == 0 and self.config.bitrate <= 1000:
                logging.debug('ideal grain is 0, but bitrate is low, setting ideal grain to 1')
                ideal_grain = 1

        rate_search_start = time.time()

        ideal_rate = self.complexity_rate_estimation()

        print(f'{self.log_prefix()}rate search took: {int(time.time() - rate_search_start)}s')
        self.stats.rate_search_time = int(time.time() - rate_search_start)

        self.job.chunk.end_override = -1

        if ideal_rate == -1:
            raise Exception('ideal_rate is -1')

        print(f'{self.log_prefix()}ideal bitrate: {ideal_rate}')

        return ideal_grain, int(ideal_rate)

    def log_prefix(self) -> str:
        return f"[{self.job.current_scene_index}] "

    def run(self):
        if self.remove_probes:
            shutil.rmtree(self.get_probe_file_base(self.job.encoded_scene_path), ignore_errors=True)

        try:
            ideal_grain, ideal_rate = self.get_ideal_grain_bitrate()
        except Exception as e:
            logging.error(f'{self.log_prefix()}error while getting ideal grain or bitrate')
            logging.error(e)
            return

        final_encode_start = time.time()
        if not os.path.exists(self.job.encoded_scene_path):
            # encode with ideal grain and bitrate

            enc = AbstractEncoderSvtenc()
            enc.bias_pct = self.bias_pct

            enc.eat_job_config(job=self.job, config=self.config)

            enc.update(
                passes=2,
                svt_grain_synth=ideal_grain,
                bitrate=ideal_rate,
                rate_distribution=RateDistribution.VBR
            )

            try:
                enc.run(timeout_value=self.final_encode_timeout)
            except Exception as e:
                print(f'{self.log_prefix()}error while encoding: {e}')

        final_vmaf = get_video_vmeth(self.job.encoded_scene_path, self.job.chunk, uhd_model=True,
                                     disable_enchancment_gain=True)

        final_bitrate = int(get_total_bitrate(self.job.encoded_scene_path) / 1000)

        print(
            f'{self.log_prefix()}final stats:'
            f' vmaf={final_vmaf} '
            f' time={int(time.time() - final_encode_start)}s '
            f' bitrate={final_bitrate}k'
        )

        self.stats.vmaf_score = final_vmaf
        self.stats.bitrate = final_bitrate
        self.stats.time_taken = int(time.time() - final_encode_start)
        self.stats.filesize = os.path.getsize(self.job.encoded_scene_path)
        self.stats.filesize_human = sizeof_fmt(self.stats.filesize)

        return self.stats
