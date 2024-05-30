import os
import pickle
from concurrent.futures import ThreadPoolExecutor
from typing import List

from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


def calulcate_ssimdb(bitrate: int, chunk: ChunkObject, dbs: List[float], ctx):
    """
    Calculates the ssim dB for a chunk and appends it to the dbs list
    :param ctx: AlabamaContext
    :param bitrate: bitrate in kbps
    :param chunk: chunk to calculate ssim dB for
    :param dbs: The list to append the ssim dB to
    """
    enc = ctx.get_encoder()
    enc.chunk = chunk
    enc.speed = 6
    enc.passes = 3
    enc.grain_synth = 0
    enc.rate_distribution = EncoderRateDistribution.VBR
    enc.threads = 1
    enc.bitrate = bitrate
    enc.output_path = (
        f"{ctx.temp_folder}adapt/bitrate/ssim_translate/{chunk.chunk_index}"
        f"{enc.get_chunk_file_extension()}"
    )
    try:
        stats: EncodeStats = enc.run(calcualte_ssim=True)
    except Exception as e:
        print(f"Failed to calculate ssim dB for {chunk.chunk_index}: {e}")
        return
    ctx.log(f"[{chunk.chunk_index}] {bitrate} kbps -> {stats.ssim_db} ssimdb")
    dbs.append(stats.ssim_db)


def get_target_ssimdb(bitrate: int, ctx, chunk_sequence) -> float:
    """
    Since in the AutoBitrate we are targeting ssim dB values, we need to somehow translate vmaf to ssim dB
    :param ctx: AlabamaContext
    :param chunk_sequence: ChunkSequence
    :param bitrate: bitrate in kbps
    :return: target ssimdb
    """
    print(f"Getting target ssim dB for {bitrate} kbps")
    cache_path = f"{ctx.temp_folder}/adapt/bitrate/ssim_translate/{bitrate}.pl"
    if os.path.exists(cache_path):
        target_ssimdb = pickle.load(open(cache_path, "rb"))
        print(f"cached ssim dB for {bitrate}: {target_ssimdb}dB")
        return target_ssimdb
    dbs = []
    os.makedirs(f"{ctx.temp_folder}/adapt/bitrate/ssim_translate", exist_ok=True)

    chunks = chunk_sequence.get_test_chunks_out_of_a_sequence(7)

    with ThreadPoolExecutor(max_workers=3) as executor:
        for chunk in chunks:
            executor.submit(calulcate_ssimdb, bitrate, chunk, dbs, ctx)
        executor.shutdown()

    target_ssimdb = sum(dbs) / len(dbs)

    print(f"Avg ssim dB for {bitrate}Kbps: {target_ssimdb}dB")
    pickle.dump(target_ssimdb, open(cache_path, "wb"))
    return target_ssimdb


def setup_ssimdb_target(ctx: AlabamaContext, sequence: ChunkSequence):
    if all(
        [
            ctx.crf_based_vmaf_targeting is False,
            ctx.vbr_perchunk_optimisation,
        ]
    ):
        if ctx.prototype_encoder.bitrate is None:
            print("No bitrate set, cannot set SSIMDB target, set --bitrate")
            quit()
        print("Using SSIMDB target")
        ctx.ssim_db_target = get_target_ssimdb(
            ctx.prototype_encoder.bitrate, ctx=ctx, chunk_sequence=sequence
        )

    return ctx
