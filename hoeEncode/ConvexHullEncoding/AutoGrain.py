import copy
import logging
import os
import pickle
import random
import time
from multiprocessing import Pool
from statistics import mean
from typing import List

from hoeEncode.ConvexHullEncoding.RdPoint import RdPoint
from hoeEncode.encode.ffmpeg.FfmpegUtil import syscmd, get_image_butteraugli_score, get_image_psnr_score, \
    get_image_ssim_score, get_image_vmaf_score


def find_lowest_x(x_list: List[float], y_list: List[float]) -> float:
    # Check that x_list and y_list are the same length
    if len(x_list) != len(y_list):
        raise ValueError("x_list and y_list must have the same length")

    # Find the minimum y-value and its index
    min_y, min_y_idx = min((y, idx) for idx, y in enumerate(y_list))

    # If the minimum y-value is at the beginning or end of the list, return the corresponding x-value
    if min_y_idx == 0:
        return x_list[0]
    elif min_y_idx == len(y_list) - 1:
        return x_list[-1]

    # Otherwise, use linear interpolation to find the x-value that corresponds to the minimum y-value
    x0 = x_list[min_y_idx - 1]
    x1 = x_list[min_y_idx]
    y0 = y_list[min_y_idx - 1]
    y1 = y_list[min_y_idx]
    slope = (y1 - y0) / (x1 - x0)
    x_min = (min_y - y0) / slope + x0

    return x_min


class AutoGrain:

    def __init__(self, **kwargs):
        self.encoded_scene_path = kwargs.get("test_file_path")
        self.chunk = kwargs.get("chunk")
        self.crf = kwargs.get("crf", 13)
        self.bitrate = kwargs.get("bitrate", None)

    do_all_metrics = False  # measure PSNR SSIM and VMAF
    keep_avifs = False  # keep the avif's after we're done measuring their stats
    remove_files_after_use = True  # don't keep the png's since they can get big

    def grain_probes(self) -> List[RdPoint]:

        test_cache_filename = self.encoded_scene_path + ".grainButter.pt"
        if os.path.exists(test_cache_filename):
            # read the file and return
            return pickle.load(open(test_cache_filename, "rb"))

        from hoeEncode.encode.encoderImpl.Svtenc import AvifEncoderSvtenc

        avif_enc = AvifEncoderSvtenc()

        if self.bitrate is not None:
            avif_enc.update(bitrate=self.bitrate)
        else:
            avif_enc.update(crf=self.crf)

        avif_enc.update(bit_depth=10)

        # Create a reference png
        ref_png = self.encoded_scene_path + ".png"
        if not os.path.exists(ref_png):
            cvmand = f"ffmpeg -y {self.chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 " + ref_png
            syscmd(cvmand)
            if not os.path.exists(ref_png):
                raise Exception("Could not create reference png")

        avif_enc.update(in_path=ref_png)

        results = []

        grain_probes = [0, 1, 4, 6, 11, 16, 21, 26]
        for grain in grain_probes:
            avif_enc.update(grain_synth=grain, output_path=self.encoded_scene_path + ".grain" + str(grain) + ".avif")
            avif_enc.run()

            if not os.path.exists(avif_enc.output_path):
                raise Exception("Encoding of avif Failed")

            decoded_test_png_path = avif_enc.output_path + ".png"

            # turn the avif into a png
            syscmd(f"ffmpeg -y -i {avif_enc.output_path} {decoded_test_png_path}")


            rd = RdPoint()
            rd.grain = grain
            rd.butter = get_image_butteraugli_score(ref_png, decoded_test_png_path)

            if self.do_all_metrics:
                rd.psnr = get_image_psnr_score(ref_png, decoded_test_png_path)
                rd.ssim = get_image_ssim_score(ref_png, decoded_test_png_path)
                rd.vmaf = get_image_vmaf_score(ref_png, decoded_test_png_path)

            if self.remove_files_after_use:
                os.remove(decoded_test_png_path)

            if not self.keep_avifs:
                os.remove(avif_enc.output_path)

            logging.debug(f"tested grain {grain}")
            results.append(rd)

        if self.remove_files_after_use:
            os.remove(ref_png)

        pickle.dump(results, open(test_cache_filename, "wb"))
        return results

    def get_ideal_grain_butteraugli(self) -> int:
        logging.debug("getting ideal grain for butteraugli")
        start = time.time()

        from hoeEncode.encode.ffmpeg.FfmpegUtil import doesBinaryExist
        if not doesBinaryExist('butteraugli'):
            raise Exception("butteraugli not found in path, fix path/install it")

        runs: List[RdPoint] = self.grain_probes()

        # find the film-grain value that corresponds to the lowest butteraugli score
        ideal_grain = find_lowest_x([point.grain for point in runs],
                                    [point.butter for point in runs])

        logging.debug(f"ideal grain is {ideal_grain}, in {time.time() - start} seconds")
        return int(ideal_grain)


def wrapper(obj):
    return obj.get_ideal_grain_butteraugli()


def get_best_avg_grainsynth(**kwargs) -> int:
    cache_filename = kwargs.get("cache_filename")
    if cache_filename is not None and os.path.exists(cache_filename):
        return pickle.load(open(cache_filename, "rb"))

    temp_folder = kwargs.get("temp_folder", "./test")
    if not os.path.exists(temp_folder):
        raise Exception(f"temp_folder {temp_folder} does not exist")

    input_file = kwargs.get("input_file")
    if input_file is None:
        raise Exception("input_file is required")

    scenes = kwargs.get("scenes")
    if scenes is None:
        raise Exception("scenes is required")
    # create a copy of the object, so it doesn't cause trouble
    scenes = copy.deepcopy(scenes)

    logging.info('starting autograin test')

    # pick random x scenes from the list
    if 'scene_pick_seed' in kwargs:
        random.seed(kwargs.get('scene_pick_seed'))

    random.shuffle(scenes)

    # how many random scenes to pick and do the test on
    random_pick = kwargs.get("random_pick", 3)
    scenes = scenes[:random_pick]

    # turn the scenes into chunk objects
    from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
    chunks_for_processing = [ChunkObject(path=input_file,
                                         first_frame_index=scene[0],
                                         last_frame_index=scene[1]) for scene in scenes]

    # create the autograin objects
    autograin_objects = [AutoGrain(chunk=chunk,
                                   test_file_path=f'{temp_folder}/{chunks_for_processing.index(chunk)}',
                                   crf=20)
                         for chunk in chunks_for_processing]

    # using multiprocessing to do the tests on all the scenes
    with Pool() as p:
        results = p.map(wrapper, autograin_objects)
        # and close the pool
        p.close()
        p.join()

    # get the results
    logging.info(f"for {random_pick} random scenes, the average ideal grain is {int(mean(results))}")
    if cache_filename is not None:
        pickle.dump(int(mean(results)), open(cache_filename, "wb"))
    return int(mean(results))
