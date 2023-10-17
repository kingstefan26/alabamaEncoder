"""
Testing the implementation of auto grain synth
"""

from alabamaEncode.adaptive.sub.grain import get_best_avg_grainsynth

if __name__ == "__main__":
    print("Test 27: AutoGrainSynth")

    input_file = "../../test.mkv"

    scene_list = None

    # avg test
    grain = get_best_avg_grainsynth(scenes=scene_list, input_file=input_file)
    print("result: " + str(grain))
