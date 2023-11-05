"""
Testing/evaluating autoParam
"""

import os

from alabamaEncode.adaptive.sub.param import AutoParam
from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.experiments.util.ExperimentUtil import get_test_files
from alabamaEncode.scene.sequence import ChunkSequence
from alabamaEncode.scene.split import get_video_scene_list_skinny

if __name__ == "__main__":
    test_folder = os.path.abspath("./tst/")
    input_file = get_test_files()[0]

    config = AlabamaContext()
    config.temp_folder = test_folder
    config.grain_synth = 4

    scenes: ChunkSequence = get_video_scene_list_skinny(
        input_file=input_file,
        max_scene_length=10,
        cache_file_path=f"{test_folder}/scenes_skinny.pt",
    )

    ab = AutoParam(scenes, config)

    best_qm = ab.get_best_qm()

    print(f"Best qm: {best_qm}")
