"""
Testing & experimenting with auto bitrate ladders
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
    config = AlabamaContext()
    config.temp_folder = test_folder
    config.grain_synth = 4

    scenes_skinny: ChunkSequence = get_video_scene_list_skinny(
        input_file=input_file,
        cache_file_path="/home/kokoniara/dev/VideoSplit/temp_201/sceneCache.pt",
        max_scene_length=10,
    )

    ab = AutoBitrateLadder(scenes_skinny, config)

    best_bitrate = ab.get_best_bitrate(skip_cache=True)

    print(f"Best bitrate: {best_bitrate}")
