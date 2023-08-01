import copy
import os
import pickle
import random
import time
from multiprocessing import Pool
from statistics import mean
from typing import List

from alabamaEncode.encoders.encoderImpl.Svtenc import AvifEncoderSvtenc
from alabamaEncode.ffmpegUtil import doesBinaryExist, get_image_butteraugli_score
from alabamaEncode.sceneSplit.ChunkOffset import ChunkObject
from alabamaEncode.sceneSplit.Chunks import ChunkSequence
from alabamaEncode.utils.execute import syscmd


class RdPoint:
    butter: float
    grain: int


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
    def __init__(self, test_file_path, chunk, bitrate=-1, crf=13, vf=""):
        self.encoded_scene_path = test_file_path
        self.chunk = chunk
        self.crf = crf
        self.bitrate = bitrate
        self.vf = vf

    keep_avifs = False  # keep the avif's after we're done measuring their stats
    remove_files_after_use = True  # don't keep the png's since they can get big

    def grain_probes(self) -> List[RdPoint]:
        test_cache_filename = self.encoded_scene_path + ".grainButter.pt"
        if os.path.exists(test_cache_filename):
            # read the file and return
            return pickle.load(open(test_cache_filename, "rb"))

        if "vf" not in self.vf and self.vf != "":
            self.vf = f"-vf {self.vf}"

        avif_enc = AvifEncoderSvtenc()

        if self.bitrate is not None:
            avif_enc.update(bitrate=self.bitrate)
        else:
            avif_enc.update(crf=self.crf)

        avif_enc.update(bit_depth=10)

        # Create a reference png
        ref_png = self.encoded_scene_path + ".png"
        if not os.path.exists(ref_png):
            cvmand = f"ffmpeg -hide_banner -y {self.chunk.get_ss_ffmpeg_command_pair()} {self.vf} -frames:v 1 {ref_png}"

            out = syscmd(cvmand)
            if not os.path.exists(ref_png):
                print(cvmand)
                raise Exception("Could not create reference png: " + out)

        avif_enc.update(in_path=ref_png)

        results = []

        grain_probes = [0, 1, 4, 6, 11, 16, 21, 26]
        for grain in grain_probes:
            avif_enc.update(
                grain_synth=grain,
                output_path=self.encoded_scene_path + ".grain" + str(grain) + ".avif",
            )
            avif_enc.run()

            if not os.path.exists(avif_enc.output_path):
                raise Exception("Encoding of avif Failed")

            decoded_test_png_path = avif_enc.output_path + ".png"

            # turn the avif into a png
            syscmd(f"ffmpeg -y -i {avif_enc.output_path} {decoded_test_png_path}")

            if not os.path.exists(decoded_test_png_path):
                raise Exception("Could not create decoded png")

            rd = RdPoint()
            rd.grain = grain
            rd.butter = get_image_butteraugli_score(ref_png, decoded_test_png_path)

            if self.remove_files_after_use:
                os.remove(decoded_test_png_path)

            if not self.keep_avifs:
                os.remove(avif_enc.output_path)

            print(f"grain {grain} -> {rd.butter} butteraugli")
            results.append(rd)

        if self.remove_files_after_use:
            os.remove(ref_png)

        pickle.dump(results, open(test_cache_filename, "wb"))
        return results

    def get_ideal_grain_butteraugli(self) -> int:
        print("getting ideal grain using butteraugli")
        start = time.time()

        if not doesBinaryExist("butteraugli"):
            raise Exception("butteraugli not found in path, fix path/install it")

        runs: List[RdPoint] = self.grain_probes()

        # find the film-grain value that corresponds to the lowest butteraugli score
        ideal_grain = find_lowest_x(
            [point.grain for point in runs], [point.butter for point in runs]
        )

        print(f"ideal grain is {ideal_grain}, in {int(time.time() - start)} seconds")
        return int(ideal_grain)


def wrapper(obj):
    return obj.get_ideal_grain_butteraugli()


def get_best_avg_grainsynth(
    cache_filename: str,
    input_file: str,
    scenes: ChunkSequence,
    scene_pick_seed: int,
    temp_folder="./grain_test",
    random_pick=6,
    bitrate=-1,
    crf=20,
    video_filters: str = "",
) -> int:
    if cache_filename is not None and os.path.exists(cache_filename):
        return pickle.load(open(cache_filename, "rb"))

    if not os.path.exists(temp_folder):
        raise Exception(f"temp_folder {temp_folder} does not exist")

    # turn temp folder into a full path
    temp_folder = os.path.abspath(temp_folder)
    # make /adapt/grain dir
    os.makedirs(f"{temp_folder}/adapt/grain", exist_ok=True)

    if input_file is None:
        raise Exception("input_file is required")

    if scenes is None:
        raise Exception("scenes is required")
    # create a copy of the object, so it doesn't cause trouble
    scenes = copy.deepcopy(scenes)

    print("starting autograin test")

    # bases on length, remove every x scene from the list so its shorter
    scenes.chunks = scenes.chunks[:: int(len(scenes.chunks) / 10)]

    # pick random x scenes from the list
    random.seed(scene_pick_seed)

    random.shuffle(scenes.chunks)

    # how many random scenes to pick and do the test on
    chunks_for_processing: List[ChunkObject] = scenes.chunks[:random_pick]

    # create the autograin objects
    if bitrate == -1:
        autograin_objects = [
            AutoGrain(
                chunk=chunk,
                test_file_path=f"{temp_folder}/adapt/grain/{chunks_for_processing.index(chunk)}",
                crf=crf,
                vf=video_filters,
            )
            for chunk in chunks_for_processing
        ]
    else:
        autograin_objects = [
            AutoGrain(
                chunk=chunk,
                test_file_path=f"{temp_folder}/adapt/grain/{chunks_for_processing.index(chunk)}",
                bitrate=bitrate,
                vf=video_filters,
            )
            for chunk in chunks_for_processing
        ]

    # using multiprocessing to do the experiments on all the scenes
    with Pool() as p:
        results = p.map(wrapper, autograin_objects)
        # and close the pool
        p.close()
        p.join()

    # get the results
    print(
        f"for {random_pick} random scenes, the average ideal grain is {int(mean(results))}"
    )
    if cache_filename is not None:
        pickle.dump(int(mean(results)), open(cache_filename, "wb"))
    return int(mean(results))
