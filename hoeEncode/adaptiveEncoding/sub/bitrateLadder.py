"""
A class that helps us find the best bitrate. Refer to class docstring
"""
import asyncio
import copy
import os
import pickle
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import List

from hoeEncode.adaptiveEncoding.sub.bitrate import get_ideal_bitrate
from hoeEncode.adaptiveEncoding.util import get_test_chunks_out_of_a_sequence
from hoeEncode.encoders import EncoderConfig
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import get_video_vmeth, get_video_ssim
from hoeEncode.parallelEncoding.Command import BaseCommandObject
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.Chunks import ChunkSequence


class AutoBitrateCacheObject:
    """
    A class that helps us cache the results of the bitrate ladder
    """

    def __init__(self, bitrate: int, ssim_db: float):
        self.bitrate = bitrate
        self.ssim_db = ssim_db


class AutoBitrateLadder:
    """
    When doing VBR encoding, a problem is to figure out what bitrate to target,
    often we just close out eyes and shoot a dart hoping 2Mbps or something is good enough.
    This is my attempt at finding a base bitrate for a given quality level for given content at a given resolution,
     automatically and hopefully better than a human intuition.
    """

    def __init__(self, chunk_sequence: ChunkSequence, config: EncoderConfig):
        self.chunk_sequence = chunk_sequence
        self.config: EncoderConfig = config

        self.chunks = get_test_chunks_out_of_a_sequence(
            self.chunk_sequence, self.random_pick_count
        )

    random_pick_count = 7
    num_probes = 6
    max_bitrate = 5000
    simultaneous_probes = 3

    def delete_best_bitrate_cache(self):
        """
        Delete the cache file for get_best_bitrate
        """
        path = f"{self.config.temp_folder}/adapt/bitrate/cache.pt"
        if os.path.exists(path):
            os.remove(path)

    def get_best_bitrate(self, skip_cache=False) -> int:
        """
        Doing a binary search on chunks, to find a bitrate that, on average, will yield config.vmaf
        :return: bitrate in kbps e.g., 2420
        """
        print("Finding best bitrate")
        probe_folder = f"{self.config.temp_folder}/adapt/bitrate/"

        if not skip_cache:
            if os.path.exists(probe_folder + "cache.pt"):
                try:
                    print("Found cache file, reading")
                    avg_best = pickle.load(open(probe_folder + "cache.pt", "rb"))
                    print(f"Best avg bitrate: {avg_best} kbps")
                    return avg_best
                except:
                    pass

        shutil.rmtree(probe_folder, ignore_errors=True)
        os.makedirs(probe_folder)

        print(
            f'Probing chunks: {" ".join([str(chunk.chunk_index) for chunk in self.chunks])}'
        )

        chunks = copy.deepcopy(self.chunks)

        # add proper paths
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.chunk_path = f"{probe_folder}{i}.ivf"

        # chunk_runs_bitrates = []
        # pool = ThreadPool(processes=self.simultaneous_probes)
        # for result in pool.imap_unordered(self.best_bitrate_single, chunks):
        #     chunk_runs_bitrates.append(result)
        # pool.close()
        # pool.join()

        commands = [GetBestBitrate(self, chunk) for chunk in chunks]

        from hoeEncode.__main__ import execute_commands

        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            execute_commands(
                self.config.use_celery,
                commands,
                self.config.multiprocess_workers,
                override_sequential=False,
            )
        )

        chunk_runs_bitrates = [command.best_bitrate for command in commands]

        avg_best = int(sum(chunk_runs_bitrates) / len(chunk_runs_bitrates))

        print(f"Best avg bitrate: {avg_best} kbps")

        if self.config.crf_bitrate_mode:
            print(
                f"Using crf bitrate mode, finding crf that matches the target bitrate"
            )
            target_crf = self.get_target_crf(avg_best)
            print(f"Avg crf for {avg_best}Kpbs: {target_crf}")
            self.config.crf = target_crf
            self.config.max_bitrate = int(avg_best * 1.6)

        try:
            print("Saving bitrate ladder detection cache file")
            pickle.dump(avg_best, open(probe_folder + "cache.pt", "wb"))
        except:
            print("Failed to save cache file for best average bitrate")

        return avg_best

    def best_bitrate_single(self, chunk: ChunkObject) -> int:
        """
        :param chunk: chunk that we will be testing
        :return: ideal bitrate for that chunk based on self.config's vmaf
        """
        encoder = AbstractEncoderSvtenc()
        encoder.eat_job_config(job=EncoderJob(chunk=chunk), config=self.config)
        encoder.update(
            speed=6,
            passes=3,
            svt_grain_synth=self.config.grain_synth,
            rate_distribution=RateDistribution.VBR,
            threads=1,
        )
        encoder.svt_bias_pct = 90

        runs = []

        left = 0
        right = self.max_bitrate
        num_probes = 0

        while left <= right and num_probes < self.num_probes:
            num_probes += 1
            mid = (left + right) // 2
            encoder.update(bitrate=mid)
            encoder.run(timeout_value=300)
            mid_vmaf = get_video_vmeth(
                chunk.chunk_path,
                chunk,
                crop_string=self.config.crop_string,
                disable_enchancment_gain=True,
                uhd_model=True,
            )
            self.config.log(f"[{chunk.chunk_index}] {mid} kbps -> {mid_vmaf} vmaf")

            runs.append((mid, mid_vmaf))

            if mid_vmaf < self.config.vmaf:
                left = mid + 1
            else:
                right = mid - 1

        # find two points that are closest to the target vmaf
        # point1 = min(runs, key=lambda x: abs(x[1] - self.config.vmaf))
        # runs.remove(point1)
        # point2 = min(runs, key=lambda x: abs(x[1] - self.config.vmaf))

        # linear interpolation to find the bitrate that gives us the target vmaf
        # best_inter = point1[0] + (point2[0] - point1[0]) * (self.config.vmaf - point1[1]) / (point2[1] - point1[1])
        # if best_inter > self.max_bitrate:
        #     best_inter = self.max_bitrate
        #
        # if best_inter < 0:
        #     print(f'{chunk.log_prefix()}vmaf linar interpolation failed, using most fitting point {point1[0]}')
        #     best_inter = point1[0]
        # best_inter = point1[0]

        best_inter = min(runs, key=lambda x: abs(x[1] - self.config.vmaf))[0]

        self.config.log(
            f"[{chunk.chunk_index}] best interpolated bitrate {best_inter} kbps",
            level=1,
        )
        return int(best_inter)

    def remove_ssim_translate_cache(self):
        """
        Removes the ssim translate cache
        """
        shutil.rmtree(f"{self.config.temp_folder}/adapt/bitrate/ssim_translate")

    def get_target_ssimdb(self, bitrate: int):
        """
        Since in the AutoBitrate we are targeting ssim dB values, we need to somehow translate vmaf to ssim dB
        :param bitrate: bitrate in kbps
        :return: target ssimdb
        """
        print(f"Getting target ssim dB for {bitrate} kbps")
        cache_path = (
            f"{self.config.temp_folder}/adapt/bitrate/ssim_translate/{bitrate}.pl"
        )
        if os.path.exists(cache_path):
            try:
                target_ssimdb = pickle.load(open(cache_path, "rb"))
                print(f"cached ssim dB for {bitrate}: {target_ssimdb}dB")
                return target_ssimdb
            except:
                pass
        dbs = []
        os.makedirs(
            f"{self.config.temp_folder}/adapt/bitrate/ssim_translate", exist_ok=True
        )

        with ThreadPoolExecutor(max_workers=self.simultaneous_probes) as executor:
            for chunk in self.chunks:
                executor.submit(self.calulcate_ssimdb, bitrate, chunk, dbs)
            executor.shutdown()

        target_ssimdb = sum(dbs) / len(dbs)

        print(f"Avg ssim dB for {bitrate}Kbps: {target_ssimdb}dB")
        try:
            pickle.dump(target_ssimdb, open(cache_path, "wb"))
        except:
            pass
        return target_ssimdb

    def calulcate_ssimdb(self, bitrate: int, chunk: ChunkObject, dbs: List[float]):
        """
        Calculates the ssim dB for a chunk and appends it to the dbs list
        :param bitrate: bitrate in kbps
        :param chunk: chunk to calculate ssim dB for
        :param dbs: The list to append the ssim dB to
        """
        encoder = AbstractEncoderSvtenc()
        encoder.eat_job_config(job=EncoderJob(chunk=chunk), config=self.config)
        encoder.update(
            speed=6,
            passes=3,
            svt_grain_synth=self.config.grain_synth,
            rate_distribution=RateDistribution.VBR,
            threads=1,
        )
        encoder.update(
            output_path=f"{self.config.temp_folder}/adapt/bitrate/ssim_translate/{chunk.chunk_index}.ivf"
        )
        encoder.svt_bias_pct = 90
        encoder.update(bitrate=bitrate)
        encoder.run(timeout_value=300)
        (ssim, ssim_db) = get_video_ssim(
            encoder.output_path, chunk, get_db=True, crop_string=self.config.crop_string
        )
        self.config.log(f"[{chunk.chunk_index}] {bitrate} kbps -> {ssim_db} ssimdb")
        dbs.append(ssim_db)

    def get_target_crf(self, bitrate: int) -> int:
        """
        Translate a bitrate roughly to a crf value
        :param bitrate: bitrate in kbps
        :return: the predicted crf
        """
        crfs = []
        for chunk in self.chunks:
            encoder = AbstractEncoderSvtenc()
            encoder.eat_job_config(job=EncoderJob(chunk=chunk), config=self.config)
            encoder.update(
                speed=4,
                passes=1,
                svt_grain_synth=self.config.grain_synth,
                rate_distribution=RateDistribution.CQ,
                threads=os.cpu_count(),
            )

            probe_folder = f"{self.config.temp_folder}/adapt/bitrate/"
            os.makedirs(probe_folder, exist_ok=True)

            max_probes = 4
            left = 0
            right = 40
            num_probes = 0

            runs = []

            while left <= right and num_probes < max_probes:
                num_probes += 1
                mid = (left + right) // 2
                encoder.update(
                    crf=mid, output_path=f"{probe_folder}{chunk.chunk_index}_{mid}.ivf"
                )
                stats = encoder.run(timeout_value=500)

                print(f"[{chunk.chunk_index}] {mid} crf -> {stats.bitrate} K")

                runs.append((mid, stats.bitrate))

                if stats.bitrate > bitrate:
                    left = mid + 1
                else:
                    right = mid - 1

            # find two points that are closest to the target bitrate
            point1 = min(runs, key=lambda x: abs(x[1] - bitrate))
            runs.remove(point1)
            point2 = min(runs, key=lambda x: abs(x[1] - bitrate))

            # linear interpolation to find the bitrate that gives us the target bitrate
            best_inter = point1[0] + (point2[0] - point1[0]) * (bitrate - point1[1]) / (
                point2[1] - point1[1]
            )
            best_inter = int(best_inter)
            print(f"[{chunk.chunk_index}] {best_inter} crf -> {bitrate} bitrate")
            crfs.append(best_inter)

        return int(sum(crfs) / len(crfs))


class GetBestBitrate(BaseCommandObject):
    """
    Wrapper around AutoBitrateLadder.get_best_bitrate to execute on our framework
    """

    def __init__(self, auto_bitrate_ladder: AutoBitrateLadder, chunk: ChunkObject):
        self.best_bitrate = None
        self.auto_bitrate_ladder = auto_bitrate_ladder
        self.chunk = chunk

    def run(self):
        self.best_bitrate = self.auto_bitrate_ladder.best_bitrate_single(self.chunk)


class GetComplexity(BaseCommandObject):
    """
    Wrapper around get_ideal_bitrate to execute on our framework
    """

    def __init__(self, chunk: ChunkObject, config: EncoderConfig):
        self.ideal_bitrate = -1
        self.chunk = chunk
        self.config = config

    def run(self):
        self.ideal_bitrate = get_ideal_bitrate(self.chunk, self.config)
