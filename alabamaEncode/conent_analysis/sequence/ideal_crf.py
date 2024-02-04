import asyncio
import copy
import os
import pickle
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from math import log
from typing import List, Tuple

from tqdm import tqdm

from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calculate import calculate_metric
from alabamaEncode.metrics.impl.vmaf import VmafOptions
from alabamaEncode.parallelEncoding.command import BaseCommandObject
from alabamaEncode.parallelEncoding.execute_commands import execute_commands
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


def get_complexity(enc: Encoder, c: ChunkObject) -> Tuple[int, float]:
    _enc = copy.deepcopy(enc)
    _enc.chunk = c
    _enc.speed = 12
    _enc.passes = 1
    _enc.rate_distribution = EncoderRateDistribution.CQ
    _enc.crf = 16
    _enc.threads = 1
    _enc.grain_synth = 0
    _enc.output_path = (
        f"/tmp/{c.chunk_index}_complexity{_enc.get_chunk_file_extension()}"
    )
    stats: EncodeStats = _enc.run()
    formula = log(stats.bitrate)
    # self.config.log(
    #     f"[{c.chunk_index}] complexity: {formula:.2f} in {stats.time_encoding}s"
    # )
    os.remove(_enc.output_path)
    return c.chunk_index, formula


class GetComplexity(BaseCommandObject):
    def __init__(self, chunk: ChunkObject, ctx):
        self.complexity = None
        self.chunk = chunk
        self.ctx = ctx

    def run(self):
        self.complexity = get_complexity(c=self.chunk, enc=self.ctx.get_encoder())


def crf_to_bitrate(
    crf: int, chunks: List[ChunkObject], ctx, simultaneous_probes=3
) -> int:
    bitrates = []

    def sub(c: ChunkObject):
        encoder = ctx.get_encoder()
        encoder.chunk = c
        probe_folder = f"{ctx.temp_folder}/adapt/crf_to_bitrate/"
        os.makedirs(probe_folder, exist_ok=True)
        encoder.speed = 5
        encoder.passes = 1
        encoder.grain_synth = ctx.prototype_encoder.grain_synth
        encoder.rate_distribution = EncoderRateDistribution.CQ
        encoder.threads = 1
        encoder.crf = crf
        encoder.output_path = (
            f"{probe_folder}{c.chunk_index}_{crf}{encoder.get_chunk_file_extension()}"
        )

        stats = encoder.run()

        print(f"[{c.chunk_index}] {crf} crf -> {stats.bitrate} kb/s")
        bitrates.append(stats.bitrate)

    with ThreadPoolExecutor(max_workers=simultaneous_probes) as executor:
        for chunk in chunks:
            executor.submit(sub, chunk)
        executor.shutdown()

    final = int(sum(bitrates) / len(bitrates))

    print(f"on avreage crf {crf} -> {final} kb/s")
    return final


def calculate_chunk_complexity(ctx, chunk_sequence) -> List[Tuple[int, float]]:
    """
    Do fast preset crf encoding on each chunk in self.chunk_sequence to get a complexity score
    :return: the ChunkSequence with complexity scores
    """
    print("Calculating chunk complexity")

    probe_folder = f"{ctx.temp_folder}/adapt/bitrate/complexity"

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

    chunk_sequence_copy = copy.deepcopy(chunk_sequence)

    encoder_extension = ctx.get_encoder().get_chunk_file_extension()

    for chunk in chunk_sequence_copy.chunks:
        chunk.chunk_path = f"{probe_folder}/{chunk.chunk_index}{encoder_extension}"

    start = time.time()

    commands = [GetComplexity(chunk) for chunk in chunk_sequence_copy.chunks]

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        execute_commands(
            ctx.use_celery,
            commands,
            -1,
        )
    )

    complexity_scores = [command.complexity for command in commands]

    print(f"Complexity calculation took {time.time() - start} seconds")

    try:
        print("Caching complexity scores")
        pickle.dump(complexity_scores, open(cache_file, "wb"))
    except:
        print("Failed to save complexity scores cache, continuing")

    for chunk in chunk_sequence.chunks:
        for index, complexity in complexity_scores:
            if index == chunk.chunk_index:
                chunk.complexity = complexity

    return complexity_scores


def best_crf_single(chunk: ChunkObject, ctx, max_crf) -> int:
    """
    :param chunk: chunk that we will be testing
    :return: ideal crf for that chunk based on self.config's vmaf
    """
    encoder = ctx.get_encoder()
    encoder.chunk = chunk
    encoder.speed = 6
    encoder.passes = 1
    encoder.rate_distribution = EncoderRateDistribution.CQ
    encoder.threads = 1

    runs = []

    left = 0
    right = max_crf
    num_probes = 0

    while left <= right and num_probes < num_probes:
        num_probes += 1
        mid_crf = (left + right) // 2
        encoder.crf = mid_crf
        encoder.run()

        mid_vmaf = calculate_metric(
            chunk=chunk,
            options=VmafOptions(
                uhd=True, neg=True, video_filters=ctx.prototype_encoder.video_filters
            ),
        ).mean

        tqdm.write(f"{chunk.log_prefix()}{mid_crf} crf -> {mid_vmaf} vmaf")

        runs.append((mid_crf, mid_vmaf))

        if mid_vmaf < ctx.vmaf:
            right = mid_crf - 1
        else:
            left = mid_crf + 1

    best_inter = min(runs, key=lambda x: abs(x[1] - ctx.vmaf))[0]

    tqdm.write(
        f"{chunk.log_prefix()}best interpolated crf {best_inter} crf",
    )
    return int(best_inter)


class GetBestCrf(BaseCommandObject):
    def __init__(self, chunk: ChunkObject, ctx):
        self.best_crf = None
        self.chunk = chunk
        self.ctx = ctx

    def run(self):
        self.best_crf = best_crf_single(self.chunk, self.ctx, max_crf=45)


def get_best_crf_guided(ctx, chunk_sequence):
    """
    :return: The best average crf found based on probing a random selection of chunks in the chunk sequence.
    """
    print("Finding best bitrate")
    probe_folder = f"{ctx.temp_folder}/adapt/crf/"

    cache_file = probe_folder + "cache.pt"
    if os.path.exists(cache_file):
        print("Found cache file, reading")
        cutoff_bitrate, avg_best_crf = pickle.load(open(cache_file, "rb"))
        print(
            f"Best avg crf: {avg_best_crf} crf; Cuttoff bitrate: {ctx.cutoff_bitrate} kbps"
        )
        ctx.cutoff_bitrate = cutoff_bitrate
        ctx.prototype_encoder.crf = avg_best_crf
        return

    shutil.rmtree(probe_folder, ignore_errors=True)
    os.makedirs(probe_folder)

    complexity_scores: List[Tuple[int, float]] = calculate_chunk_complexity()

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

    for c in chunk_sequence.chunks:
        for chunk in avg_complex_chunks:
            if c.chunk_index == chunk[0]:
                chunks_for_crf_probe.append(copy.deepcopy(c))

    print(
        f'Probing chunks: {" ".join([str(chunk.chunk_index) for chunk in chunks_for_crf_probe])}'
    )

    encoder_extension = ctx.get_encoder().get_chunk_file_extension()

    # add proper paths
    for i, chunk in enumerate(chunks_for_crf_probe):
        chunk.chunk_index = i
        chunk.chunk_path = f"{probe_folder}{i}{encoder_extension}"

    commands = [GetBestCrf(chunk, ctx) for chunk in chunks_for_crf_probe]

    asyncio.get_event_loop().run_until_complete(
        execute_commands(
            ctx.use_celery,
            commands,
            ctx.multiprocess_workers,
        )
    )

    chunk_runs_crfs = [command.best_crf for command in commands]

    avg_best_crf = int(sum(chunk_runs_crfs) / len(chunk_runs_crfs))

    print(f"Crf for 80%tile chunks matching {ctx.vmaf}VMAF: {avg_best_crf} crf")

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
    for c in chunk_sequence.chunks:
        for chunk in random_complex_chunks:
            if c.chunk_index == chunk[0]:
                chunks_for_max_probe.append(copy.deepcopy(c))

    cutoff_bitrate = crf_to_bitrate(avg_best_crf, chunks_for_max_probe, ctx)

    print("Saving crf ladder detection cache file")
    pickle.dump((cutoff_bitrate, avg_best_crf), open(cache_file, "wb"))

    ctx.cutoff_bitrate = cutoff_bitrate
    ctx.prototype_encoder.crf = avg_best_crf


def setup_ideal_crf_weighted(ctx: AlabamaContext, sequence: ChunkSequence):
    if ctx.flag1:
        get_best_crf_guided(ctx, sequence)
    return ctx
