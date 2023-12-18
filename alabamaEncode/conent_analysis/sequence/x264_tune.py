import os
import shutil
from multiprocessing import Pool

from alabamaEncode.adaptive.helpers.probe_chunks import (
    get_test_chunks_out_of_a_sequence,
)
from alabamaEncode.encoder.impl.X264 import EncoderX264


def run_tune(a):
    tune, enc, path = a
    enc.x264_tune = tune
    enc.output_path = os.path.join(path, f"{tune}{enc.get_chunk_file_extension()}")
    stats = enc.run(calculate_vmaf=True)
    print(f"{tune}: {stats.bitrate}kb/s {stats.vmaf_result.harmonic_mean}vmaf")
    return tune, stats.vmaf_result.harmonic_mean, stats.bitrate


def get_ideal_x264_tune(ctx, sequence):
    """
    Picks the ideal x264 tune for the sequence, based on the vmaf per bitrate
    This approach might be flawed but it ~works
    :param ctx:
    :param sequence:
    :return:
    """

    if isinstance(ctx.prototype_encoder, EncoderX264):
        cache_path = f"{ctx.temp_folder}x264_tune.cache"

        if os.path.exists(cache_path):
            with open(cache_path) as f:
                ctx.prototype_encoder.x264_tune = f.read()
            print(f"setting x264 tune to {ctx.prototype_encoder.x264_tune} from cache")
            return ctx

        print("picking x264 tune")
        tunes = ["animation", "film", "grain"]
        enc = ctx.get_encoder()
        enc.crf = 23
        enc.speed = 5

        path = os.path.join(ctx.temp_folder, "adapt", "x264_tune/")

        if not os.path.exists(path):
            os.makedirs(path)

        best = []

        for test_chunk in get_test_chunks_out_of_a_sequence(
            chunk_sequence=sequence, random_pick_count=2
        ):
            enc.chunk = test_chunk

            # get (tune, stats) tuples in a parallel fashion
            with Pool() as p:
                runs = p.map(run_tune, [(tune, enc.clone(), path) for tune in tunes])
                # and close the pool
                p.close()
                p.join()

            # pick the tune with the biggest vmaf per bitrate with a little bias towards vmaf
            runs_calculated = [
                (tune, ((vmaf / bitrate) + (vmaf / 100)))
                for tune, vmaf, bitrate in runs
            ]
            runs_calculated.sort(key=lambda x: x[1])
            best_tune = runs_calculated[-1][0]

            best.append(best_tune)

        # pick the most common tune from the best tunes
        ctx.prototype_encoder.x264_tune = max(set(best), key=best.count)
        print(f"picked {ctx.prototype_encoder.x264_tune} as x264 tune")
        with open(cache_path, "w") as f:
            f.write(ctx.prototype_encoder.x264_tune)

        # remove the test chunks
        shutil.rmtree(path)

    return ctx
