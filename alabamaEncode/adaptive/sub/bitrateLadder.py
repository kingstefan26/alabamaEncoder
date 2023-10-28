"""
A class that helps us find the best bitrate. Refer to class docstring
"""
import asyncio
import copy
import os
import pickle
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

from tqdm import tqdm

from alabamaEncode.adaptive.util import get_test_chunks_out_of_a_sequence
from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.encoders.encoderMisc import EncodeStats, EncoderRateDistribution
from alabamaEncode.parallelEncoding.Command import BaseCommandObject
from alabamaEncode.sceneSplit.chunk import ChunkObject, ChunkSequence
from alabamaEncode.utils.ffmpegUtil import get_video_vmeth, get_video_ssim


class AutoBitrateCacheObject:
    """
    A class that helps us cache the results of the bitrate ladder
    """

    def __init__(self, bitrate: int, ssim_db: float):
        self.bitrate = bitrate
        self.ssim_db = ssim_db


def crabby_paddy_formula(bitrate: int, speed_used: int, crf_used: int) -> float:
    """
    A formula that tries to estimate the complexity of a chunk based on the crf bitrate
    :param bitrate:  in kb/s e.g., 2420
    :param speed_used: svtav1 speed used to encode the chunk
    :param crf_used: crf used to encode the chunk
    :return: complexity score
    """
    bitrate_ = bitrate / 1000
    # remove 5% for every speed above 4
    bitrate_ -= min(0, speed_used - 4) * (bitrate_ * 0.05)
    return bitrate_


class AutoBitrateLadder:
    """
    When doing VBR encoding, a problem is to figure out what bitrate to target,
    often we just close out eyes and shoot a dart hoping 2Mbps or something is good enough.
    This is my attempt at finding a base bitrate for a given quality level for given content at a given resolution,
     automatically and hopefully better than human intuition.
    Or just use crf nerd.
    """

    def __init__(self, chunk_sequence: ChunkSequence, config: AlabamaContext):
        self.chunk_sequence = chunk_sequence
        self.config: AlabamaContext = config

        self.chunks = get_test_chunks_out_of_a_sequence(
            self.chunk_sequence, self.random_pick_count
        )

        if len(self.chunks) == 0:
            raise Exception("No chunks to probe")

    random_pick_count = 7
    num_probes = 6
    max_bitrate = 5000
    simultaneous_probes = 3
    max_crf = 45

    def delete_best_bitrate_cache(self):
        """
        Delete the cache file for get_best_bitrate
        """
        path = f"{self.config.temp_folder}/adapt/bitrate/cache.pt"
        if os.path.exists(path):
            os.remove(path)

    def get_complexity(self, c: ChunkObject) -> Tuple[int, float]:
        enc = self.config.get_encoder()
        enc.setup(chunk=c, config=self.config)
        enc.update(
            speed=12,
            passes=1,
            rate_distribution=EncoderRateDistribution.CQ,
            crf=16,
            threads=1,
            grain_synth=0,
        )
        timetook = time.time()
        stats: EncodeStats = enc.run()
        formula = crabby_paddy_formula(stats.bitrate, enc.speed, enc.crf)
        tqdm.write(
            f"[{c.chunk_index}] complexity: {formula:.2f} in {time.time() - timetook:.2f}s"
        )
        os.remove(c.chunk_path)
        return c.chunk_index, formula

    def calculate_chunk_complexity(self) -> List[Tuple[int, float]]:
        """
        Do fast preset crf encoding on each chunk in self.chunk_sequence to get a complexity score
        :return: the ChunkSequence with complexity scores
        """
        print("Calculating chunk complexity")

        probe_folder = f"{self.config.temp_folder}/adapt/bitrate/complexity"

        # make sure the folder exists
        if not os.path.exists(probe_folder):
            os.makedirs(probe_folder)

        cache_file = f"{probe_folder}/cache.pt"
        if os.path.exists(cache_file):
            try:
                print("Found cache file, reading")
                complexity_scores = pickle.load(open(probe_folder + "cache.pt", "rb"))
                return complexity_scores
            except:
                print("Failed to read cache file, continuing")

        chunk_sequence_copy = copy.deepcopy(self.chunk_sequence)

        encoder_extension = self.config.get_encoder().get_chunk_file_extension()

        for chunk in chunk_sequence_copy.chunks:
            chunk.chunk_path = f"{probe_folder}/{chunk.chunk_index}{encoder_extension}"

        start = time.time()

        commands = [GetComplexity(self, chunk) for chunk in chunk_sequence_copy.chunks]

        from alabamaEncode.__main__ import execute_commands

        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            execute_commands(
                self.config.use_celery,
                commands,
                -1,
                override_sequential=False,
            )
        )

        complexity_scores = [command.complexity for command in commands]

        print(f"Complexity calculation took {time.time() - start} seconds")

        try:
            print("Caching complexity scores")
            pickle.dump(complexity_scores, open(cache_file, "wb"))
        except:
            print("Failed to save complexity scores cache, continuing")

        for chunk in self.chunk_sequence.chunks:
            for index, complexity in complexity_scores:
                if index == chunk.chunk_index:
                    chunk.complexity = complexity

        return complexity_scores

    def get_best_crf_guided(self) -> int:
        """
        :return: The best average bitrate found based on probing a random selection of chunks in the chunk sequence.
        """
        print("Finding best bitrate")
        probe_folder = f"{self.config.temp_folder}/adapt/crf/"

        if os.path.exists(probe_folder + "cache.pt"):
            try:
                print("Found cache file, reading")
                avg_best = pickle.load(open(probe_folder + "cache.pt", "rb"))
                print(f"Best avg crf: {avg_best} crf")
                return avg_best
            except:
                pass

        shutil.rmtree(probe_folder, ignore_errors=True)
        os.makedirs(probe_folder)

        complexity_scores: List[Tuple[int, float]] = self.calculate_chunk_complexity()

        # sort chunks by complexity
        complexity_scores.sort(key=lambda x: x[1])

        # get the 90tile complexity chunks
        n = len(complexity_scores)

        # Calculate 10th percentile (for the lower end)
        p10_index = int(0.1 * n)

        # Calculate 90th percentile (for the upper end)
        p90_index = int(0.9 * n)

        # Your average complexity chunks are those lying between the 10th and 90th percentile
        avg_complex_chunks = [complexity_scores[i] for i in range(p10_index, p90_index)]

        avg_complex_chunks = random.sample(
            avg_complex_chunks, min(10, len(avg_complex_chunks))
        )

        chunks_for_crf_probe = []

        for c in self.chunk_sequence.chunks:
            for chunk in avg_complex_chunks:
                if c.chunk_index == chunk[0]:
                    chunks_for_crf_probe.append(copy.deepcopy(c))

        print(
            f'Probing chunks: {" ".join([str(chunk.chunk_index) for chunk in chunks_for_crf_probe])}'
        )

        encoder_extension = self.config.get_encoder().get_chunk_file_extension()

        # add proper paths
        for i, chunk in enumerate(chunks_for_crf_probe):
            chunk.chunk_index = i
            chunk.chunk_path = f"{probe_folder}{i}{encoder_extension}"

        commands = [GetBestCrf(self, chunk) for chunk in chunks_for_crf_probe]

        from alabamaEncode.__main__ import execute_commands

        asyncio.get_event_loop().run_until_complete(
            execute_commands(
                self.config.use_celery,
                commands,
                self.config.multiprocess_workers,
                override_sequential=False,
            )
        )

        chunk_runs_crfs = [command.best_crf for command in commands]

        avg_best = int(sum(chunk_runs_crfs) / len(chunk_runs_crfs))

        print(f"Crf for 80%tile chunks matching {self.config.vmaf}VMAF: {avg_best} crf")

        try:
            print("Saving bitrate ladder detection cache file")
            pickle.dump(avg_best, open(probe_folder + "cache.pt", "wb"))
        except:
            print("Failed to save cache file for best average bitrate")

        print("Probing top 5%tile complex chunks for cutoff bitrate")

        # get the top 5% most complex chunks no less than five, unless the number of chunks is less than 5
        top_complex_chunks = complexity_scores[
            -max(10, int(len(complexity_scores) * 0.05)) :
        ]

        # get a random 30% of the top 5% most complex chunks

        random_complex_chunks = random.sample(
            top_complex_chunks, int(len(top_complex_chunks) * 0.30)
        )

        chunks_for_max_probe = []
        for c in self.chunk_sequence.chunks:
            for chunk in random_complex_chunks:
                if c.chunk_index == chunk[0]:
                    chunks_for_max_probe.append(copy.deepcopy(c))

        cutoff_bitreate = self.crf_to_bitrate(avg_best, chunks_for_max_probe)

        self.config.cutoff_bitrate = cutoff_bitreate
        self.config.crf = avg_best

        return avg_best

    def get_cutoff_bitrate_from_crf(self, crf):
        probe_folder = f"{self.config.temp_folder}/adapt/crf_to_bitrate/"

        if os.path.exists(probe_folder + "cache.pt"):
            try:
                print("Found cache file, reading")
                avg_best = pickle.load(open(probe_folder + "cache.pt", "rb"))
                print(f"Best avg crf: {avg_best} crf")
                return avg_best
            except:
                pass

        shutil.rmtree(probe_folder, ignore_errors=True)
        os.makedirs(probe_folder)

        complexity_scores: List[Tuple[int, float]] = self.calculate_chunk_complexity()

        # sort chunks by complexity
        complexity_scores.sort(key=lambda x: x[1])

        # get the top 5% most complex chunks no less than ten, unless the number of chunks is less than ten
        top_complex_chunks = complexity_scores[
            -max(10, int(len(complexity_scores) * 0.05)) :
        ]

        # get a random 30% of the top 5% most complex chunks
        random_complex_chunks = random.sample(
            top_complex_chunks, int(len(top_complex_chunks) * 0.30)
        )

        chunks_for_max_probe = []
        for c in self.chunk_sequence.chunks:
            for chunk in random_complex_chunks:
                if c.chunk_index == chunk[0]:
                    chunks_for_max_probe.append(copy.deepcopy(c))

        cutoff_bitreate = self.crf_to_bitrate(crf, chunks_for_max_probe)
        self.config.cutoff_bitrate = cutoff_bitreate
        return cutoff_bitreate

    def get_best_bitrate_guided(self) -> int:
        """
        :return: The best average bitrate found based on probing a random selection of chunks in the chunk sequence.
        """
        print("Finding best bitrate")
        probe_folder = f"{self.config.temp_folder}/adapt/bitrate/"

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

        complexity_scores = self.calculate_chunk_complexity()

        # sort chunks by complexity
        complexity_scores.sort(key=lambda x: x[1])

        # get the top 5% most complex chunks no less than five, unless the number of chunks is less than 5
        top_complex_chunks = complexity_scores[
            -max(10, int(len(complexity_scores) * 0.05)) :
        ]

        # get a random 30% of the top 5% most complex chunks

        random_complex_chunks = random.sample(
            top_complex_chunks, int(len(top_complex_chunks) * 0.30)
        )

        chunks = []

        for c in self.chunk_sequence.chunks:
            for chunk in random_complex_chunks:
                if c.chunk_index == chunk[0]:
                    chunks.append(copy.deepcopy(c))

        print(
            f'Probing chunks: {" ".join([str(chunk.chunk_index) for chunk in chunks])}'
        )

        encoder_extension = self.config.get_encoder().get_chunk_file_extension()

        # add proper paths
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.chunk_path = f"{probe_folder}{i}{encoder_extension}"

        commands = [GetBestBitrate(self, chunk) for chunk in chunks]

        from alabamaEncode.__main__ import execute_commands

        asyncio.get_event_loop().run_until_complete(
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

        encoder_extension = self.config.get_encoder().get_chunk_file_extension()

        # add proper paths
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.chunk_path = f"{probe_folder}{i}{encoder_extension}"

        # chunk_runs_bitrates = []
        # pool = ThreadPool(processes=self.simultaneous_probes)
        # for result in pool.imap_unordered(self.best_bitrate_single, chunks):
        #     chunk_runs_bitrates.append(result)
        # pool.close()
        # pool.join()

        commands = [GetBestBitrate(self, chunk) for chunk in chunks]

        from alabamaEncode.__main__ import execute_commands

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
        encoder = self.config.get_encoder()
        encoder.setup(chunk=chunk, config=self.config)
        encoder.update(
            speed=6,
            passes=3,
            grain_synth=self.config.grain_synth,
            rate_distribution=EncoderRateDistribution.VBR,
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
                video_filters=self.config.video_filters,
                disable_enchancment_gain=True,
                uhd_model=True,
            )
            tqdm.write(f"{chunk.log_prefix()}{mid} kbps -> {mid_vmaf} vmaf")

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

        tqdm.write(
            f"{chunk.log_prefix()}best interpolated bitrate {best_inter} kbps",
        )
        return int(best_inter)

    def best_crf_single(self, chunk: ChunkObject) -> int:
        """
        :param chunk: chunk that we will be testing
        :return: ideal crf for that chunk based on self.config's vmaf
        """
        encoder = self.config.get_encoder()
        encoder.setup(chunk=chunk, config=self.config)
        encoder.update(
            speed=6,
            passes=3,
            grain_synth=self.config.grain_synth,
            rate_distribution=EncoderRateDistribution.CQ,
            threads=1,
        )

        runs = []

        left = 0
        right = self.max_crf
        num_probes = 0

        while left <= right and num_probes < self.num_probes:
            num_probes += 1
            mid = (left + right) // 2
            encoder.update(crf=mid)
            encoder.run(timeout_value=300)
            mid_vmaf = get_video_vmeth(
                chunk.chunk_path,
                chunk,
                video_filters=self.config.video_filters,
                disable_enchancment_gain=True,
                uhd_model=True,
            )
            tqdm.write(f"{chunk.log_prefix()}{mid} crf -> {mid_vmaf} vmaf")

            runs.append((mid, mid_vmaf))

            if mid_vmaf < self.config.vmaf:
                right = mid - 1
            else:
                left = mid + 1

        best_inter = min(runs, key=lambda x: abs(x[1] - self.config.vmaf))[0]

        tqdm.write(
            f"{chunk.log_prefix()}best interpolated crf {best_inter} crf",
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
        encoder = self.config.get_encoder()
        encoder.setup(chunk=chunk, config=self.config)
        encoder.update(
            speed=6,
            passes=3,
            grain_synth=self.config.grain_synth,
            rate_distribution=EncoderRateDistribution.VBR,
            threads=1,
        )
        encoder.update(
            output_path=f"{self.config.temp_folder}/adapt/bitrate/ssim_translate/{chunk.chunk_index}{encoder.get_chunk_file_extension()}"
        )
        encoder.svt_bias_pct = 90
        encoder.update(bitrate=bitrate)
        encoder.run(timeout_value=300)
        (ssim, ssim_db) = get_video_ssim(
            encoder.output_path,
            chunk,
            get_db=True,
            crop_string=self.config.video_filters,
        )
        self.config.log(f"[{chunk.chunk_index}] {bitrate} kbps -> {ssim_db} ssimdb")
        dbs.append(ssim_db)

    def crf_to_bitrate(self, crf: int, chunks: List[ChunkObject]) -> int:
        bitrates = []

        def sub(c: ChunkObject):
            encoder = self.config.get_encoder()
            encoder.setup(chunk=c, config=self.config)
            probe_folder = f"{self.config.temp_folder}/adapt/crf_to_bitrate/"
            os.makedirs(probe_folder, exist_ok=True)
            encoder.update(
                speed=5,
                passes=1,
                grain_synth=self.config.grain_synth,
                rate_distribution=EncoderRateDistribution.CQ,
                threads=1,
                crf=crf,
                output_path=f"{probe_folder}{c.chunk_index}_{crf}{encoder.get_chunk_file_extension()}",
            )

            stats = encoder.run(timeout_value=500)

            print(f"[{c.chunk_index}] {crf} crf ~> {stats.bitrate} bitrate")
            bitrates.append(stats.bitrate)

        with ThreadPoolExecutor(max_workers=self.simultaneous_probes) as executor:
            for chunk in chunks:
                executor.submit(sub, chunk)
            executor.shutdown()

        final = int(sum(bitrates) / len(bitrates))

        print(f"on avreage crf {crf} -> {final} kb/s")
        return final

    def get_target_crf(self, bitrate: int) -> int:
        """
        Translate a bitrate roughly to a crf value
        :param bitrate: bitrate in kbps
        :return: the predicted crf
        """
        crfs = []

        def sub(c: ChunkObject):
            encoder = self.config.get_encoder()
            encoder.setup(chunk=c, config=self.config)
            encoder.update(
                speed=5,
                passes=1,
                grain_synth=self.config.grain_synth,
                rate_distribution=EncoderRateDistribution.CQ,
                threads=1,
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
                    crf=mid,
                    output_path=f"{probe_folder}{c.chunk_index}_{mid}{encoder.get_chunk_file_extension()}",
                )
                stats = encoder.run(timeout_value=500)

                print(f"[{c.chunk_index}] {mid} crf ~> {stats.bitrate} kb/s")

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
            print(
                f"[{c.chunk_index}] INTERPOLATED: {best_inter} crf ~> {bitrate} bitrate"
            )
            crfs.append(best_inter)

        with ThreadPoolExecutor(max_workers=self.simultaneous_probes) as executor:
            for chunk in self.chunks:
                executor.submit(sub, chunk)
            executor.shutdown()

        final = int(sum(crfs) / len(crfs))

        print(f"Average crf for {bitrate} -> {final}")
        return final


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


class GetBestCrf(BaseCommandObject):
    def __init__(self, auto_bitrate_ladder: AutoBitrateLadder, chunk: ChunkObject):
        self.best_crf = None
        self.autobitrate_ladder = auto_bitrate_ladder
        self.chunk = chunk

    def run(self):
        self.best_crf = self.autobitrate_ladder.best_crf_single(self.chunk)


class GetComplexity(BaseCommandObject):
    def __init__(self, auto_bitrate_ladder: AutoBitrateLadder, chunk: ChunkObject):
        self.complexity = None
        self.auto_bitrate_ladder = auto_bitrate_ladder
        self.chunk = chunk

    def run(self):
        self.complexity = self.auto_bitrate_ladder.get_complexity(self.chunk)
