"""
A class that helps us find the best bitrate. Refer to class docstring
"""
import copy
import os
import pickle
import random
import shutil
from multiprocessing.pool import ThreadPool
from typing import List

from hoeEncode.encoders import EncoderConfig
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import get_video_vmeth, get_video_ssim
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

    random_pick_count = 5
    num_probes = 3
    max_bitrate = 4000
    simultaneous_probes = 3

    def best_bitrate_single(self, chunk: ChunkObject) -> int:
        """
        :param chunk: chunk that we will be testing
        :return: ideal bitrate for that chunk based on self.config's vmaf
        """
        encoder = AbstractEncoderSvtenc()
        encoder.eat_job_config(job=EncoderJob(chunk=chunk), config=self.config)
        encoder.update(speed=6, passes=3, svt_grain_synth=self.config.grain_synth,
                       rate_distribution=RateDistribution.VBR, threads=1)
        encoder.bias_pct = 90

        runs = []

        left = 0
        right = self.max_bitrate
        num_probes = 0

        while left <= right and num_probes < self.num_probes:
            num_probes += 1
            mid = (left + right) // 2
            encoder.update(bitrate=mid)
            encoder.run(timeout_value=300)
            mid_vmaf = get_video_vmeth(chunk.chunk_path, chunk, crop_string=self.config.crop_string)
            print(f'[{chunk.chunk_index}] {mid} kbps -> {mid_vmaf} vmaf')

            runs.append((mid, mid_vmaf))

            if mid_vmaf < self.config.vmaf:
                left = mid + 1
            else:
                right = mid - 1

        # find two points that are closest to the target vmaf
        point1 = min(runs, key=lambda x: abs(x[1] - self.config.vmaf))
        runs.remove(point1)
        point2 = min(runs, key=lambda x: abs(x[1] - self.config.vmaf))

        # linear interpolation to find the bitrate that gives us the target vmaf
        best_inter = point1[0] + (point2[0] - point1[0]) * (self.config.vmaf - point1[1]) / (point2[1] - point1[1])
        if best_inter > self.max_bitrate:
            best_inter = self.max_bitrate

        if best_inter < 0:
            print(f'{chunk.log_prefix()} vmaf linar interpolation failed, using most fitting point {point1[0]}')
            best_inter = point1[0]

        print(f'[{chunk.chunk_index}] best interpolated bitrate {best_inter} kbps')
        return int(best_inter)

    def get_target_ssimdb(self, bitrate: int, random_chunks: List[ChunkObject]):
        """
        Since in the AutoBitrate we are targeting ssim dB values, we need to somehow translate vmaf to ssim dB
        :param bitrate: bitrate in kbps
        :return: target ssimdb
        """
        dbs = []
        for chunk in random_chunks:
            encoder = AbstractEncoderSvtenc()
            encoder.eat_job_config(job=EncoderJob(chunk=chunk), config=self.config)
            encoder.update(speed=6, passes=3, svt_grain_synth=self.config.grain_synth,
                           rate_distribution=RateDistribution.VBR, threads=1)
            encoder.bias_pct = 90
            encoder.update(bitrate=bitrate)
            encoder.run(timeout_value=300)
            (ssim, ssim_db) = get_video_ssim(chunk.chunk_path, chunk, get_db=True,
                                             crop_string=self.config.crop_string)
            print(f'[{chunk.chunk_index}] {bitrate} kbps -> {ssim_db} ssimdb')
            dbs.append(ssim_db)

        return sum(dbs) / len(dbs)

    def get_best_bitrate(self, cache_file: str = 'cache.pt', skip_cache=False) -> int:
        """
        we are not actually targeting vmaf here, but using vmaf as score for perceptual quality
        :return: bitrate in kbps
        """

        print('Finding best bitrate')
        probe_folder = f'{self.config.temp_folder}/adapt/bitrate/'

        if not skip_cache:
            if os.path.exists(probe_folder + cache_file):
                try:
                    print('Found cache file, reading')
                    avg_best = pickle.load(open(probe_folder + cache_file, "rb"))
                    print(f'Best avg bitrate: {avg_best} kbps')
                    return avg_best
                except:
                    pass

        shutil.rmtree(probe_folder, ignore_errors=True)
        os.makedirs(probe_folder)

        # binary search on three random chunks (in the middle) to find a bitrate that gives us the target vmaf
        chunks_copy: List[ChunkObject] = copy.deepcopy(self.chunk_sequence.chunks)
        chunks_copy = chunks_copy[int(len(chunks_copy) * 0.2):int(len(chunks_copy) * 0.8)]
        random.shuffle(chunks_copy)
        chunks = chunks_copy[:self.random_pick_count]
        chunks: List[ChunkObject] = copy.deepcopy(chunks)

        print(f'Probing chunks {" ".join([str(chunk.chunk_index) for chunk in chunks])}')

        # add proper paths
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.chunk_path = f'{probe_folder}{i}.ivf'

        # do a num_probes deep binary search, starting at starting_point and looking checking if vmaf fits,
        # at the end do a liner interpolation to get the ideal bitrate
        # to do that for every chunk and avg the bitrate
        chunk_runs_bitrates = []
        pool = ThreadPool(processes=self.simultaneous_probes)
        for result in pool.imap_unordered(self.best_bitrate_single, chunks):
            chunk_runs_bitrates.append(result)
        pool.close()
        pool.join()

        avg_best = int(sum(chunk_runs_bitrates) / len(chunk_runs_bitrates))

        print(f'Best avg bitrate: {avg_best} kbps')

        print(f'Translating to ssimdb')
        target_ssimdb = self.get_target_ssimdb(avg_best, chunks)
        print(f'Target ssimdb: {target_ssimdb}')
        self.config.ssim_db_target = target_ssimdb

        try:
            print('Saving cache file')
            pickle.dump(avg_best, open(probe_folder + cache_file, "wb"))
        except:
            print('Failed to save cache file for best average bitrate')

        return avg_best
