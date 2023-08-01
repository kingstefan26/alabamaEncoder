"""
testing the fake two pass that i implemented, aka bitrate_adjust_mode = 'full'
"""
import os

from alabamaEncode.adaptiveEncoding.sub.bitrateLadder import AutoBitrateLadder
from alabamaEncode.encoders.EncoderConfig import EncoderConfigObject
from alabamaEncode.sceneSplit.Chunks import ChunkSequence
from alabamaEncode.sceneSplit.split import get_video_scene_list_skinny


def fake_two_pass():
    bitrate_being_evaluated = 2000

    config = EncoderConfigObject(
        temp_folder=testing_env, bitrate=bitrate_being_evaluated
    )
    config.use_celery = False

    ab = AutoBitrateLadder(chunk_sequence, config)
    config.ssim_db_target = ab.get_target_ssimdb(config.bitrate)

    ab.ration_bitrate(chunk_sequence)


def auto_bitrate_getter():
    config = EncoderConfigObject(temp_folder=testing_env)
    config.use_celery = False

    ab = AutoBitrateLadder(chunk_sequence, config)

    # ab.get_best_bitrate()

    ab.delete_best_bitrate_cache()

    ab.num_probes = 6

    ab.get_best_bitrate()


if __name__ == "__main__":
    source_path = "/mnt/data/downloads/Silo.S01E05.1080p.WEB.H264-CAKES[rarbg]/silo.s01e05.1080p.web.h264-cakes.mkv"

    testing_env = "./tst/"
    if not os.path.exists(testing_env):
        os.mkdir(testing_env)

    chunk_sequence: ChunkSequence = get_video_scene_list_skinny(
        input_file=source_path,
        cache_file_path=testing_env + "sceneCache.pt",
        max_scene_length=10,
    )
    for xyz in chunk_sequence.chunks:
        xyz.chunk_path = f"{testing_env}{xyz.chunk_index}.ivf"

    fake_two_pass()
    # auto_bitrate_getter()
