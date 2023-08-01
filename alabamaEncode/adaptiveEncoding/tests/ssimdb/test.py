"""
Testing the ssim dB targeting technique
"""
import copy
import os
from typing import List

from alabamaEncode.adaptiveEncoding.sub.bitrate import get_ideal_bitrate
from alabamaEncode.adaptiveEncoding.sub.bitrateLadder import AutoBitrateLadder
from alabamaEncode.adaptiveEncoding.util import get_test_chunks_out_of_a_sequence
from alabamaEncode.encoders.EncoderConfig import EncoderConfigObject
from alabamaEncode.sceneSplit.ChunkOffset import ChunkObject
from alabamaEncode.sceneSplit.Chunks import ChunkSequence
from alabamaEncode.sceneSplit.split import get_video_scene_list_skinny


def test():
    source_path = "/mnt/data/downloads/Silo.S01E05.1080p.WEB.H264-CAKES[rarbg]/silo.s01e05.1080p.web.h264-cakes.mkv"

    testing_env = "./tstSsimDb/"
    if not os.path.exists(testing_env):
        os.mkdir(testing_env)

    chunk_sequence: ChunkSequence = get_video_scene_list_skinny(
        input_file=source_path,
        cache_file_path=testing_env + "sceneCache.pt",
        max_scene_length=10,
    )

    bitrate_being_evaluated = 2000

    ab = AutoBitrateLadder(chunk_sequence, EncoderConfigObject(temp_folder=testing_env))
    ab.remove_ssim_translate_cache()
    ssim_db_target = ab.get_target_ssimdb(bitrate_being_evaluated)

    config = EncoderConfigObject(
        temp_folder=testing_env,
        ssim_db_target=ssim_db_target,
        bitrate=bitrate_being_evaluated,
    )

    chunks = get_test_chunks_out_of_a_sequence(chunk_sequence, 10)
    test_chunks: List[ChunkObject] = copy.deepcopy(chunks)
    for i, chunk in enumerate(test_chunks):
        chunk.chunk_index = i
        chunk.chunk_path = f"{testing_env}chunk{i}.ivf"

    for i in range(5):
        get_ideal_bitrate(test_chunks[i], config, show_rate_calc_log=True)


if __name__ == "__main__":
    test()
