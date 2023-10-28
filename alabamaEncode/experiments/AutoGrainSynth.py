"""
Testing the implementation of auto grain synth
"""
from alabamaEncode.adaptive.sub.grain import get_best_avg_grainsynth
from alabamaEncode.experiments.util.ExperimentUtil import get_test_files

if __name__ == "__main__":
    print("Test 27: AutoGrainSynth")

    input_file = get_test_files()[0]

    scene_list = None

    # avg test
    grain = get_best_avg_grainsynth(scenes=scene_list, input_file=input_file)
    print("result: " + str(grain))
