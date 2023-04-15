import copy
import logging
import math
import os
import pickle
import shutil
import time
from typing import List, Callable

from hoeEncode.ConvexHullEncoding.AutoGrain import AutoGrain
from hoeEncode.ConvexHullEncoding.RdPoint import RdPoint
from hoeEncode.encode.encoderImpl.RateDiss import RateDistribution
from hoeEncode.encode.encoderImpl.Aomenc import AbstractEncoderAomEnc
from hoeEncode.encode.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderJob, EncoderConfigObject, get_video_vmeth, get_video_ssim, \
    get_video_psnr, get_total_bitrate, EncodingStatsObject, sizeof_fmt
from paraliezeMeHoe.ThaVaidioEncoda import KummandObject


def closest(lst, K):
    return lst[min(range(len(lst)), key=lambda i: abs(lst[i] - K))]


def find_middle(X, Y):
    # Combine the x and y arrays into a list of tuples
    curve_data = list(zip(X, Y))

    # Step 1: Calculate the length of the curve
    length = 0
    for i in range(len(curve_data) - 1):
        length += math.sqrt(
            (curve_data[i + 1][0] - curve_data[i][0]) ** 2 + (curve_data[i + 1][1] - curve_data[i][1]) ** 2)

    # Step 2: Divide the length of the curve by 2 to get the half-length
    half_length = length / 2

    # Step 3: Traverse the curve to find the point that is halfway along the length of the curve
    current_length = 0
    for i in range(len(curve_data) - 1):
        segment_length = math.sqrt(
            (curve_data[i + 1][0] - curve_data[i][0]) ** 2 + (curve_data[i + 1][1] - curve_data[i][1]) ** 2)
        if current_length + segment_length >= half_length:
            # Step 4: Interpolate between the last two points to find the point on the curve that is halfway along the length of the curve
            segment_remaining = half_length - current_length
            segment_ratio = segment_remaining / segment_length
            midpoint_x = curve_data[i][0] + (curve_data[i + 1][0] - curve_data[i][0]) * segment_ratio
            midpoint_y = curve_data[i][1] + (curve_data[i + 1][1] - curve_data[i][1]) * segment_ratio
            break
        current_length += segment_length

    return midpoint_x, midpoint_y


def linear_approximation(points: List[List[float]]) -> Callable[[float], float]:
    """
    This function approximates any y and x using linear approximation.

    Args:
    points: A list of points, where each point is a list of two numbers, (x, y).

    Returns:
    A function that takes in an x-value and returns the y-value that is the linear approximation of the points.
    """

    # Find the slope of the line.
    slope = (points[1][1] - points[0][1]) / (points[1][0] - points[0][0])

    # Find the y-intercept of the line.
    y_intercept = points[0][1] - slope * points[0][0]

    # Define the function that returns the linear approximation.
    def linear_approximation_function(x):
        return slope * x + y_intercept

    return linear_approximation_function


def linear_approximation_alt(points: List[List[float]], tapering_off_point: float = None) -> Callable[[float], float]:
    """
    This function approximates any y and x using linear approximation.

    Args:
    points: A list of points, where each point is a list of two numbers, (x, y).
    tapering_off_point: A float value where the function starts to taper off and return a constant value. If None,
        the function will not taper off.

    Returns:
    A function that takes in an x-value and returns the y-value that is the linear approximation of the points.
    """

    # Find the slope of the line.
    slope = (points[1][1] - points[0][1]) / (points[1][0] - points[0][0])

    # Find the y-intercept of the line.
    y_intercept = points[0][1] - slope * points[0][0]

    # Define the function that returns the linear approximation.
    def linear_approximation_function(x):
        if tapering_off_point is not None and x > tapering_off_point:
            return slope * tapering_off_point + y_intercept
        else:
            return slope * x + y_intercept

    return linear_approximation_function


class ConvexEncoder:

    def __init__(self, job: EncoderJob, config: EncoderConfigObject):
        self.job = job
        self.config = config
        self.stats = EncodingStatsObject()

    # what speed do we run while searching bitrate
    convex_speed = 12

    # speed for the final encode
    encode_speed = 3

    remove_probes = True  # after encoding is done remove the probes

    search_lenght_override = 24

    vmaf_compensation = 0.5

    max_crf = 40

    min_crf = 13

    threads_for_final_encode = 1

    vmaf_brokey_crf_compensation = 5

    # how long (seconds) before we time out the final encode
    # currently set to ~30 minutes
    final_encode_timeout = 1600

    flag_1 = False  # find ideal bitrate using the middle of rate curve instead of linear interpolation
    flag_2 = True  # use vmaf neg 4k model
    flag_3 = False  # use bitrate vbr instead of capped crf
    flag_4 = True  # only use 2 probes for convex hull

    # this doesn't do well when the shot starts with no motion and then some, either disable it or measure the motion in
    # advance and then toggle this on/off
    flag_5 = False  # use search_lenght_override for rate probes, aka only probe first x frames

    flag_6 = False  # use precomputed vmaf modifier to compansate speed 12 loss
    flag_7 = True  # for low bitrates always use at least 1 grain

    # if we get two points eg 98 98.5 the curve will be a very high, trying to predict vmaf eg 94 on that curve
    # will give some crazy crf value like 120, in a effort to fix it. when predicted vmaf gets higher than the max
    # we set it to min + contant value eg 13 + 5 = 18 as a middle ground, proper fix would be:
    # 1. use diffrent metric that isnt so unstable, eg ssim2
    # 2. use a better curve fitting algorithm
    # 3. somehow add bias to the curve
    # 4. use machine learing to predict the curve
    # 5. make svt not trick vmaf
    flag_9 = True  # fix vmeth being going cray cray when rate probes are too close together

    flag_10 = True  # dont process other metrics other than vmaf
    flag_11 = False  # calculate the ideal grain regardless of config object, can yield -10% size gains
    flag_12 = True  # put rate probes in new folders
    flag_13 = True  # use tune psnr instead of Vq for probes
    flag_14 = True  # use complexity to get bitrate
    flag_15 = False  # use aomenc
    flag_16 = 16  # what crf to use for complexity, higher yields lower avg bitrate
    flag_17 = True  # dont allow the complexity to go over 0
    flag_18 = False  # calculate complexity but with a bitrate cap set to target bitrate
    flag_19 = False  # use vbr instead of crf for complexity
    flag_21 = (False, 15)  # --bias-pct using svtenc

    def complexity_rate_estimation(self, ignore_cache=False):
        probe_file_base = self.get_probe_name()
        cache_filename = probe_file_base + '.complexity.speed' + str(self.convex_speed) + '.pt'

        # check if we have already done this
        if os.path.exists(cache_filename) and ignore_cache is False:
            return pickle.load(open(cache_filename, 'rb'))

        crf = self.flag_16
        test_probe_path = probe_file_base + 'complexity.probe.ivf'

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
                   crf=crf,
                   output_path=test_probe_path)

        if self.flag_18 is True:
            enc.update(bitrate=self.config.bitrate, rate_distribution=RateDistribution.CQ_VBV)
        else:
            enc.update(rate_distribution=RateDistribution.CQ, crf=crf)

        enc.run(override_if_exists=False)

        # psnr = get_video_psnr(test_probe_path, self.job.chunk)
        ssim = get_video_ssim(test_probe_path, self.job.chunk)
        try:
            bitrate = get_total_bitrate(test_probe_path)
        except Exception as e:
            print(e)
            print(f"Failed to get bitrate for {test_probe_path} aborting this chunk")
            os.remove(test_probe_path)
            return -1

        complexity = bitrate
        complexity /= 1000000
        complexity /= ssim
        complexity -= 1
        complexity /= 2

        if self.flag_17 is True:
            if complexity > 0:
                complexity = 0

        target_bitrate = self.config.bitrate
        target_bitrate = float(target_bitrate) * 1000
        abr_rate = (target_bitrate * complexity) + target_bitrate
        abr_rate /= 1000
        k_ = f'{self.log_prefix()}===============\n' \
             f'{self.log_prefix()} wanted bitrate: {target_bitrate / 1000}k\n' \
             f'{self.log_prefix()} bitrate using crf {self.flag_16}: {int(bitrate / 1000)}k\n' \
             f'{self.log_prefix()} ssim: {ssim}\n' \
             f'{self.log_prefix()} complexity: {complexity}\n' \
             f'{self.log_prefix()} complexity = min((((bitrate / 1000000) / ssim) - 1) / 2, 0)\n' \
             f'{self.log_prefix()} theoredical ABR rate = (target * complexity) + target = {abr_rate}k \n' \
             f'{self.log_prefix()}==============='
        print(k_)

        if self.remove_probes:
            os.remove(test_probe_path)

        pickle.dump(abr_rate, open(cache_filename, 'wb'))
        return abr_rate

    def complexity_rate_estimation_2(self, ignore_cache=False):
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
                   output_path=test_probe_path)

        enc.update(bitrate=self.config.bitrate, rate_distribution=RateDistribution.VBR)

        enc.run(override_if_exists=False)

        ssim = get_video_ssim(test_probe_path, self.job.chunk)
        try:
            bitrate = get_total_bitrate(test_probe_path)
        except Exception as e:
            print(e)
            print(f"Failed to get bitrate for {test_probe_path} aborting this chunk")
            os.remove(test_probe_path)
            return -1

        complexity = bitrate
        complexity /= 1000000
        complexity /= ssim
        complexity -= 1
        complexity /= 2
        complexity += 1

        # clamp between 0.5 and 1.5
        complexity = max(0.5, min(1.5, complexity))

        target_bitrate = self.config.bitrate

        abr_rate = target_bitrate * complexity

        print(
            f'{self.log_prefix()}===============\n'
            f'{self.log_prefix()} wanted bitrate: {target_bitrate}k\n'
            f'{self.log_prefix()} ssim when using target bitrate: {ssim}\n'
            f'{self.log_prefix()} complexity: max(0.5, min(1.5, bitrate / 1000000 / ssim - 1 / 2 + 1)) = {complexity}\n'
            f'{self.log_prefix()} theoredical ABR rate: target * complexity = {abr_rate}k \n'
            f'{self.log_prefix()}==============='
        )

        if self.remove_probes:
            os.remove(test_probe_path)

        pickle.dump(abr_rate, open(cache_filename, 'wb'))
        return abr_rate

    def create_rd_point(self, **kwargs):
        path: str = kwargs.get('path')
        speed: int = kwargs.get('speed')
        grain: int = kwargs.get('grain')
        bitrate: str = kwargs.get('rate')

        rd_point = RdPoint()

        if self.flag_2:
            rd_point.vmaf = get_video_vmeth(distorted_path=path,
                                            in_chunk=self.job.chunk,
                                            uhd_model=True,
                                            disable_enchancment_gain=True)
        else:
            rd_point.vmaf = get_video_vmeth(path, self.job.chunk)

        if self.flag_10 is False:
            rd_point.ssim = get_video_ssim(path, self.job.chunk)
            rd_point.psnr = get_video_psnr(path, self.job.chunk)

        rd_point.rate = get_total_bitrate(path)
        rd_point.target_rate = bitrate
        rd_point.speed = speed
        rd_point.file_path = path
        rd_point.grain = grain

        if self.remove_probes:
            os.remove(path)

        return rd_point

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
        probe_file_base = copy.deepcopy(self.job.encoded_scene_path)
        if self.flag_12:
            probe_file_base = self.get_probe_file_base(self.job.encoded_scene_path)
        return probe_file_base

    def rate_tests(self, speed=12, grain=0):
        probe_file_base = self.get_probe_name()

        cache_filename = probe_file_base + f'.bitrate.speed{speed}.grain{grain}.pt'

        # check if we have already done this
        if os.path.exists(cache_filename):
            return pickle.load(open(cache_filename, 'rb'))

        from hoeEncode.encode.encoderImpl.Svtenc import AbstractEncoderSvtenc

        enc = AbstractEncoderSvtenc()
        enc.update(speed=speed,
                   passes=1,
                   temp_folder=self.config.temp_folder,
                   chunk=self.job.chunk,
                   svt_grain_synth=grain,
                   current_scene_index=self.job.current_scene_index)

        if self.flag_13:
            enc.update(tune=1)

        runs = []

        if self.flag_3 is True:

            bitrates = [250, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000, 7000]

            if self.flag_4 is True:
                bitrates = [500, 4000]

            for bitrate in bitrates:
                enc.bitrate = bitrate
                print(f'Testing bitrate {bitrate}')

                test_probe_path = probe_file_base + f'.bitrate{bitrate}.speed{speed}.ivf'
                enc.update(output_path=test_probe_path)
                enc.run(override_if_exists=False)
                runs.append(self.create_rd_point(path=test_probe_path, speed=speed, grain=grain, rate=bitrate))

        else:
            if self.config.bitrate == 0:
                raise Exception('bitrate is 0')
            enc.update(bitrate=self.config.bitrate)

            crfs = [10, 14, 16, 20, 25, 30, 35, 40, 45]

            if self.flag_4 is True:
                crfs = [self.min_crf, self.max_crf]

            for crf in crfs:
                print(f'Testing crf: {crf}')
                enc.update(crf=crf)

                test_probe_path = probe_file_base + f'.crf{crf}.speed{speed}.ivf'
                enc.update(output_path=test_probe_path)
                enc.run(override_if_exists=False)
                runs.append(self.create_rd_point(path=test_probe_path, speed=speed, grain=grain, rate=crf))

        # save the file
        pickle.dump(runs, open(cache_filename, 'wb'))

        return runs

    def get_ideal_bitrate(self, speed: int, grain=0) -> int:
        runs = self.rate_tests(speed, grain=grain)

        if self.flag_1 is True:
            # get middle of the convex hull
            bitrate, ssim = find_middle([point.target_rate for point in runs],
                                        [point.ssim for point in runs])
            return int(bitrate)
        else:
            if self.flag_6 is True:
                graph_points: List[List[float]] = [[point.vmaf + self.vmaf_compensation, point.target_rate]
                                                   for point in runs]
            else:
                graph_points: List[List[float]] = [[point.vmaf, point.target_rate] for point in runs]

            linear_approximation_function = linear_approximation(graph_points)

            ideal_rate = linear_approximation_function(self.config.vmaf)

            if self.flag_9 is True and ideal_rate > self.max_crf:
                ideal_rate = self.min_crf + self.vmaf_brokey_crf_compensation

            return int(ideal_rate)

    def calculate_vmaf_compensation(self) -> float:
        """
        when running at higher presets the hq will be lower,
        here im trying to compensate for that in the vmaf
        :return:
        """
        pass

    def get_ideal_grain_bitrate(self):
        if self.flag_5 is True:
            logging.debug('using rate probe frame-lenght override: ' + str(self.search_lenght_override))
            self.job.chunk.end_override = self.search_lenght_override

        if self.flag_11 is False:
            if self.config.grain_synth is None or self.config.grain_synth == -1:
                raise Exception('grain_synth is None or -1')
            ideal_grain = self.config.grain_synth
        else:
            if self.flag_12:
                auto_grain = AutoGrain(chunk=self.job.chunk,
                                       test_file_path=self.get_probe_file_base(self.job.encoded_scene_path))
            else:
                auto_grain = AutoGrain(chunk=self.job.chunk, test_file_path=self.job.encoded_scene_path)

            ideal_grain = auto_grain.get_ideal_grain_butteraugli()
            logging.debug('ideal grain (butteraugli method): ' + str(ideal_grain))

        if self.flag_7 is True:
            if ideal_grain == 0 and self.config.bitrate <= 1000:
                logging.debug('ideal grain is 0, but bitrate is low, setting ideal grain to 1')
                ideal_grain = 1

        rate_search_start = time.time()

        if self.flag_14 is True:
            self.flag_3 = True
            if self.flag_19 is True:
                ideal_rate = self.complexity_rate_estimation_2()
            else:
                ideal_rate = self.complexity_rate_estimation()
        else:
            # get ideal bitrate
            ideal_rate = self.get_ideal_bitrate(12, ideal_grain)

        print(f'{self.log_prefix()}rate search took: {int(time.time() - rate_search_start)}s')
        self.stats.rate_search_time = int(time.time() - rate_search_start)

        self.job.chunk.end_override = -1

        if ideal_rate == -1:
            raise Exception('ideal_rate is -1')

        if self.flag_3 is True:
            print(f'{self.log_prefix()}ideal bitrate: {ideal_rate}')
        else:
            print(f'{self.log_prefix()}ideal crf: {ideal_rate}')

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

            if self.flag_15 is True:
                if self.flag_21[0] is True:
                    raise Exception('flag_15 and flag_21[0] is True')
                enc = AbstractEncoderAomEnc()
            else:
                enc = AbstractEncoderSvtenc()
                if self.flag_21[0] is True:
                    enc.bias_pct = self.flag_21[1]

            enc.update(current_scene_index=self.job.current_scene_index,
                       speed=self.encode_speed,
                       passes=2,
                       temp_folder=self.config.temp_folder,
                       chunk=self.job.chunk,
                       crop_string=self.config.crop_string,
                       svt_grain_synth=ideal_grain,
                       output_path=self.job.encoded_scene_path,
                       threads=self.threads_for_final_encode)

            if self.flag_3 is True:
                enc.bitrate = ideal_rate
                enc.update(rate_distribution=RateDistribution.VBR)
            else:
                enc.crf = ideal_rate
                enc.bitrate = self.config.bitrate
                enc.update(rate_distribution=RateDistribution.CQ_VBV)

            try:
                enc.run(timeout_value=self.final_encode_timeout)
            except Exception as e:
                print(f'{self.log_prefix()}error while encoding: {e}')

        if self.flag_2:
            final_vmaf = get_video_vmeth(self.job.encoded_scene_path, self.job.chunk, uhd_model=True,
                                         disable_enchancment_gain=True)
        else:
            final_vmaf = get_video_vmeth(self.job.encoded_scene_path, self.job.chunk)

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


class ConvexKummand(KummandObject):
    def __init__(self, job: EncoderJob, config: EncoderConfigObject, convx=None):
        if job is not None and config is not None:
            self.enc = ConvexEncoder(job, config)
        elif convx is not None:
            self.enc = convx
        else:
            raise Exception('invalid constructor')

    def run(self):
        self.enc.run()
