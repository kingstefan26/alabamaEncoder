import asyncio
import copy
import os
import pickle
import shutil
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.metrics.impl.vmaf import VmafOptions
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.parallelEncoding.command import BaseCommandObject
from alabamaEncode.parallelEncoding.execute_commands import execute_commands
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


def best_bitrate_single(ctx, chunk: ChunkObject) -> int:
    """
    :param ctx: context
    :param chunk: chunk that we will be testing
    :return: ideal bitrate for that chunk based on ctx's vmaf
    """
    enc = ctx.get_encoder()
    enc.chunk = chunk
    enc.speed = 6
    enc.passes = 3
    enc.grain_synth = ctx.prototype_encoder.grain_synth
    enc.rate_distribution = EncoderRateDistribution.VBR
    enc.threads = 1

    runs = []

    left = 0
    right = 5000
    num_probes = 0

    while left <= right and num_probes < num_probes:
        num_probes += 1
        mid_bitrate = (left + right) // 2
        enc.bitrate = mid_bitrate
        mid_vmaf = enc.run(
            metric_to_calculate=Metric.VMAF,
            metric_params=VmafOptions(uhd=True, neg=True),
        ).metric_results.mean

        tqdm.write(f"{chunk.log_prefix()}{mid_bitrate} kbps -> {mid_vmaf} vmaf")

        runs.append((mid_bitrate, mid_vmaf))

        if mid_vmaf < ctx.vmaf:
            left = mid_bitrate + 1
        else:
            right = mid_bitrate - 1

    best_inter = min(runs, key=lambda x: abs(x[1] - ctx.vmaf))[0]

    tqdm.write(
        f"{chunk.log_prefix()}best interpolated bitrate {best_inter} kbps",
    )
    return int(best_inter)


def get_target_crf(bitrate: int, chunks, ctx) -> int:
    """
    Translate a bitrate roughly to a crf value
    :param ctx: context
    :param chunks: chunks to test
    :param bitrate: bitrate in kbps
    :return: the predicted crf
    """
    crfs = []

    def sub(c: ChunkObject):
        encoder = ctx.get_encoder()
        encoder.chunk = c
        encoder.speed = 5
        encoder.passes = 1
        encoder.grain_synth = ctx.prototype_encoder.grain_synth
        encoder.rate_distribution = EncoderRateDistribution.CQ
        encoder.threads = 1

        probe_folder = f"{ctx.temp_folder}/adapt/bitrate/"
        os.makedirs(probe_folder, exist_ok=True)

        max_probes = 4
        left = 0
        right = 40
        num_probes = 0

        runs = []

        while left <= right and num_probes < max_probes:
            num_probes += 1
            mid = (left + right) // 2
            encoder.crf = mid
            encoder.output_path = f"{probe_folder}{c.chunk_index}_{mid}{encoder.get_chunk_file_extension()}"
            stats = encoder.run()

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
        print(f"[{c.chunk_index}] INTERPOLATED: {best_inter} crf ~> {bitrate} bitrate")
        crfs.append(best_inter)

    with ThreadPoolExecutor(max_workers=3) as executor:
        for chunk in chunks:
            executor.submit(sub, chunk)
        executor.shutdown()

    final = int(sum(crfs) / len(crfs))

    print(f"Average crf for {bitrate} -> {final}")
    return final


class GetBestBitrate(BaseCommandObject):
    """
    Wrapper around AutoBitrateLadder.get_best_bitrate to execute on our framework
    """

    def __init__(self, chunk: ChunkObject, ctx):
        self.ctx = ctx
        self.best_bitrate = None
        self.chunk = chunk

    def run(self):
        self.best_bitrate = best_bitrate_single(self.ctx, self.chunk)


async def get_best_bitrate(ctx, chunk_sequence, skip_cache=False) -> int:
    """
    Doing a binary search on chunks, to find a bitrate that, on average, will yield config.vmaf
    :return: bitrate in kbps e.g., 2420
    """

    print("Finding best bitrate")
    probe_folder = f"{ctx.temp_folder}/adapt/bitrate/"

    chunks = chunk_sequence.get_test_chunks_out_of_a_sequence(7)

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

    print(f'Probing chunks: {" ".join([str(chunk.chunk_index) for chunk in chunks])}')

    chunks = copy.deepcopy(chunks)

    encoder_extension = ctx.get_encoder().get_chunk_file_extension()

    # add proper paths
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i
        chunk.chunk_path = f"{probe_folder}{i}{encoder_extension}"

    commands = [GetBestBitrate(chunk, ctx) for chunk in chunks]

    encode_task = asyncio.create_task(
        execute_commands(
            ctx.use_celery,
            commands,
            ctx.multiprocess_workers,
        )
    )
    await encode_task

    chunk_runs_bitrates = [command.best_bitrate for command in commands]

    avg_best = int(sum(chunk_runs_bitrates) / len(chunk_runs_bitrates))

    print(f"Best avg bitrate: {avg_best} kbps")

    if ctx.crf_bitrate_mode:
        print(f"Using crf bitrate mode, finding crf that matches the target bitrate")
        target_crf = get_target_crf(avg_best, chunks, ctx)
        print(f"Avg crf for {avg_best}Kpbs: {target_crf}")
        ctx.prototype_encoder.crf = target_crf
        ctx.max_bitrate = int(avg_best * 1.6)

    try:
        print("Saving bitrate ladder detection cache file")
        pickle.dump(avg_best, open(probe_folder + "cache.pt", "wb"))
    except:
        print("Failed to save cache file for best average bitrate")

    return avg_best


async def setup_ideal_bitrate(ctx: AlabamaContext, sequence: ChunkSequence):
    if (
        not ctx.flag1
        and ctx.crf_based_vmaf_targeting is False
        and ctx.find_best_bitrate
    ):
        print("Using ideal bitrate")
        ctx.prototype_encoder.bitrate = await get_best_bitrate(ctx, sequence)

    return ctx
