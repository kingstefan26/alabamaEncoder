"""
Testing the ssim dB targeting technique
"""
import copy
import os
from typing import List

from alabamaEncode.adaptive.sub.bitrate import get_ideal_bitrate
from alabamaEncode.adaptive.sub.bitrateLadder import AutoBitrateLadder
from alabamaEncode.adaptive.util import get_test_chunks_out_of_a_sequence
from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.experiments.util.ExperimentUtil import get_test_files
from alabamaEncode.sceneSplit.chunk import ChunkObject, ChunkSequence
from alabamaEncode.sceneSplit.split import get_video_scene_list_skinny


def test():
    source_path = get_test_files()[0]

    testing_env = "./tstSsimDb/"
    if not os.path.exists(testing_env):
        os.mkdir(testing_env)

    chunk_sequence: ChunkSequence = get_video_scene_list_skinny(
        input_file=source_path,
        cache_file_path=testing_env + "sceneCache.pt",
        max_scene_length=10,
    )

    bitrate_being_evaluated = 2000

    ab = AutoBitrateLadder(chunk_sequence, AlabamaContext(temp_folder=testing_env))
    ab.remove_ssim_translate_cache()
    ssim_db_target = ab.get_target_ssimdb(bitrate_being_evaluated)

    config = AlabamaContext(
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
