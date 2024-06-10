import os

import numpy as np

from alabamaEncode.conent_analysis.chunk.analyze_steps.new_grain import (
    calc_grainsynth_of_scene,
)
from alabamaEncode.scene.scene_detection import scene_detect


def gather_src_vals():
    test_env = "./experiments/grain_synth/"
    test_env = os.path.abspath(test_env)

    if not os.path.exists(test_env):
        os.makedirs(test_env)

    scene_list = scene_detect(
        input_file="/home/kokoniara/ep3_halo_test.mkv",
        cache_file_path=test_env + "sceneCache.pt",
    )
    output_vals = []
    for chunk in scene_list.chunks:
        src_values = calc_grainsynth_of_scene(
            chunk,
            crop_vf="3840:1920:0:120",
            scale_vf="1920:-2",
            return_source_values=True,
        )
        ref_size, weak_size, strong_size = (
            src_values["ref_size"],
            src_values["weak_size"],
            src_values["strong_size"],
        )
        # normalize using ref_size as 1
        weak_size /= ref_size
        strong_size /= ref_size
        output_vals.append([weak_size, strong_size])
    return np.array(output_vals)


if __name__ == "__main__":
    # output_vals = (
    #     # gather_src_vals()
    # )  # [[ref_size, weak_size, strong_size], ...] for each chunk
    # print(output_vals)

    output_vals = np.array(
        [
            [0.85019309, 0.83728725],
            [0.86150752, 0.8377991],
            [0.870051, 0.85019648],
            [0.87227345, 0.85443137],
            [0.86221075, 0.83221905],
            [0.87164853, 0.84443476],
            [0.87270245, 0.83833311],
            [0.84947409, 0.81849868],
            [0.86418557, 0.82854816],
        ]
    )

    training_data = [11, 9, 12, 8, 12, 14, 17, 14, 18]

    # now we figure out a arithmetic formula that takes the src values and gives us the ideal grain value,
    # using the training data
    # were going to use scipy.curve_fit to find the formula

    # TODO