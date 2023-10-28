"""
Testing & experimenting with auto bitrate ladders GUIDED BY COMPLEXITY
"""
import os

from alabamaEncode.adaptive.sub.bitrateLadder import AutoBitrateLadder
from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.experiments.util.ExperimentUtil import get_test_files
from alabamaEncode.sceneSplit.chunk import ChunkSequence
from alabamaEncode.sceneSplit.split import get_video_scene_list_skinny

if __name__ == "__main__":
    test_folder = os.path.abspath("./tst/")
    input_file = get_test_files()[0]
    config = AlabamaContext(temp_folder=test_folder, grain_synth=3)

    config.multiprocess_workers = 5

    scenes_skinny: ChunkSequence = get_video_scene_list_skinny(
        input_file=input_file,
        cache_file_path="/home/kokoniara/dev/VideoSplit/alabamaEncode/experiments/complexity_guided/scene_cache.pt",
        max_scene_length=10,
        override_bad_wrong_cache_path=True,
    )

    ab = AutoBitrateLadder(scenes_skinny, config)

    best_bitrate = ab.get_best_bitrate_guided()

    print(f"Best bitrate: {best_bitrate}")
