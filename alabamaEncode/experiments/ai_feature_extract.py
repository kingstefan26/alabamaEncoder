import json
import os

from matplotlib import pyplot as plt

from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.scene.chunk import ChunkObject

if __name__ == "__main__":
    chunk = ChunkObject(
        path="/mnt/data/objective-1-fast/Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f.y4m"
    )

    features = Ffmpeg.get_content_features(chunk)

    print(json.dumps(features, indent=4))

    # on individual plots, plot every feature, assuming that features is a dict with the key as the frame index,
    # and the value is a dict of features
    # "0": {
    #     "entropy.entropy.normal.Y": "7.232096",
    #     "entropy.normalized_entropy.normal.Y": "0.723210",
    #     ...
    # },
    # "1": {
    #     "entropy.entropy.normal.Y": "7.226429",
    #     "entropy.normalized_entropy.normal.Y": "0.722643",
    #     "entropy.entropy.normal.U": "5.048188",
    #       ...
    # },
    # "2": {
    # etc

    env = "./ai_feature_extract"
    env = os.path.abspath(env)
    if not os.path.exists(env):
        os.mkdir(env)

    plot_dir = os.path.join(env, "plots")

    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)

    plots = []

    # Organize features by their names
    organized_features = dict()
    for frame_index, feature_dict in features.items():
        for feature_name, feature_value in feature_dict.items():
            if feature_name not in organized_features:
                organized_features[feature_name] = list()
            organized_features[feature_name].append(
                (int(frame_index), float(feature_value))
            )

    # Plot all features on their individual plots
    for feature_name, values in organized_features.items():
        x_values, y_values = zip(
            *values
        )  # Unpack frame indices and respective feature values

        plt.figure(figsize=(10, 5))
        plt.scatter(
            x_values, y_values
        )  # Consider using plt.scatter for individual points
        plt.title(f"Plot for {feature_name}")
        plt.grid()
        plt.xlabel("Frame Index")
        plt.ylabel(f"{feature_name}")
        # save plot
        plt.savefig(os.path.join(plot_dir, f"{feature_name}.png"))
        plots.append(os.path.join(plot_dir, f"{feature_name}.png"))
        plt.clf()
        plt.close()

    # create mosaic
    run_cli(
        f"montage {' '.join(plots)} -geometry +0+0  {os.path.join(plot_dir, 'mosaic.png')}"
    )
