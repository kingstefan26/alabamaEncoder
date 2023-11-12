"""
Testing the implementation of auto grain synth
"""
import os

from alabamaEncode.adaptive.sub.grain2 import calc_grainsynth_of_scene
from alabamaEncode.scene.split import get_video_scene_list_skinny

if __name__ == "__main__":
    # print("Test 27: AutoGrainSynth")
    #
    # input_file = get_test_files()[0]
    #
    # scene_list = None
    #
    # # avg test
    # grain = get_best_avg_grainsynth(scenes=scene_list, input_file=input_file)
    # print("result: " + str(grain))

    print("Test 28: AutoGrainSynth")

    test_env = "./experiments/grain_synth/"

    # turn into full path
    test_env = os.path.abspath(test_env)

    if not os.path.exists(test_env):
        os.makedirs(test_env)

    input_file = "/home/kokoniara/ep3_halo_test.mkv"

    scene_list = get_video_scene_list_skinny(
        input_file=input_file,
        cache_file_path=test_env + "sceneCache.pt",
        max_scene_length=10,
    )

    for chunk in scene_list.chunks:
        calc_grainsynth_of_scene(chunk, test_env)
        print("\n\n")
