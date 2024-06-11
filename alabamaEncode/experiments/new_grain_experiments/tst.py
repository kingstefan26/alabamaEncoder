import os

import numpy as np

from alabamaEncode.conent_analysis.chunk.analyze_steps.new_grain import (
    calc_grainsynth_of_scene_fast,
)
from alabamaEncode.conent_analysis.chunk.analyze_steps.per_scene_grain import (
    calc_grainsynth_of_scene,
)
from alabamaEncode.scene.scene_detection import scene_detect


def gather_src_vals():
    test_env = "./experiments/grain_synth/"
    test_env = os.path.abspath(test_env)

    if not os.path.exists(test_env):
        os.makedirs(test_env)

    files = [
        "/home/kokoniara/ep3_halo_test.mkv",
        "/home/kokoniara/laPuczajna_fallout_2024_e1s01_testClip_ss840_t60.mkv",
        "/home/kokoniara/howlscastle_test.mkv",
    ]
    chunks = []
    for i, file in enumerate(files):
        scene_list = scene_detect(
            input_file=file,
            cache_file_path=f"{test_env}{i}_sceneCache.pt",
        )
        chunks.extend(scene_list.chunks)

    x = []
    y = []

    for chunk in chunks:
        src_values = calc_grainsynth_of_scene_fast(
            chunk,
            crop_vf="3840:1920:0:120",
            scale_vf="1920:-2",
            return_source_values=True,
        )
        try:
            grain_value = calc_grainsynth_of_scene(
                chunk,
                crop_vf="3840:1920:0:120",
                scale_vf="1920:-2",
                # parallel=True,
            )
        except RuntimeError:
            continue
        ref_size, weak_size, strong_size = (
            src_values["ref_size"],
            src_values["weak_size"],
            src_values["strong_size"],
        )
        # normalize using ref_size as 1
        weak_size /= ref_size
        strong_size /= ref_size
        print(f"weak: {weak_size}, strong: {strong_size}, grain: {grain_value}")
        x.append([weak_size, strong_size])
        y.append(grain_value)

    return x, y


if __name__ == "__main__":
    load = True
    if load:
        output_vals = np.load("output_vals.npy")
        training_data = np.load("training_data.npy")
    else:
        output_vals, training_data = gather_src_vals()
        output_vals = np.array(output_vals)

        # save
        np.save("output_vals.npy", output_vals)
        np.save("training_data.npy", training_data)

    print(f"Processed {len(training_data)} chunks")

    data = output_vals
    answers = training_data

    # output_vals = np.array(
    #     [
    #         [0.85019309, 0.83728725],
    #         [0.86150752, 0.8377991],
    #         [0.870051, 0.85019648],
    #         [0.87227345, 0.85443137],
    #         [0.86221075, 0.83221905],
    #         [0.87164853, 0.84443476],
    #         [0.87270245, 0.83833311],
    #         [0.84947409, 0.81849868],
    #         [0.86418557, 0.82854816],
    #     ]
    # )
    #
    # training_data = np.array([11, 9, 12, 8, 12, 14, 17, 14, 18])

    def polynomial_features(X, degree):
        from itertools import combinations_with_replacement

        n_samples, n_features = X.shape
        combinations = list(combinations_with_replacement(range(n_features), degree))
        X_poly = np.ones((n_samples, len(combinations)))

        for i, index_comb in enumerate(combinations):
            X_poly[:, i] = np.prod(X[:, index_comb], axis=1)

        return X_poly

    # Define the model function
    def predict(X, weights):
        return np.dot(X, weights)

    # Normal Equation method to find optimal weights
    def fit_normal_equation(X, y):
        X_b = np.c_[np.ones((X.shape[0], 1)), X]  # Add bias term
        return np.linalg.inv(X_b.T.dot(X_b)).dot(X_b.T).dot(y)

    # Create polynomial features
    degree = 2
    data_poly = polynomial_features(data, degree)

    weights = fit_normal_equation(data_poly, answers)

    def inference(new_data, weights, degree):
        new_data_poly = polynomial_features(new_data, degree)
        new_data_poly_b = np.c_[
            np.ones((new_data_poly.shape[0], 1)), new_data_poly
        ]  # Add bias term
        return predict(new_data_poly_b, weights)

    predictions = inference(data, weights, degree)
    errors = np.abs(predictions - answers)
    error_percentages = (errors / answers) * 100

    for real, pred, error, error_percent in zip(
        answers, predictions, errors, error_percentages
    ):
        print(
            f"real: {real}, predicted: {pred}, error: {error}, error percent: {error_percent}"
        )

    overall_error_percent = np.mean(error_percentages)
    print(f"overall error percent: {overall_error_percent}")

    # Example usage of the inference function
    new_data = np.array([[0.850193091421479, 0.8372872506855793]])
    new_predictions = inference(new_data, weights, degree)
    print("Predictions for new data:", int(new_predictions[0]))

    # print weights without e+x syntax
    print("Model weights")
    print(np.array2string(weights, separator=", "))
