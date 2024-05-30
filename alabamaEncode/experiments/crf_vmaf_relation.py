import concurrent
import copy
import os
import pickle
from concurrent.futures import ThreadPoolExecutor as Executor
from math import log

import keras
import numpy as np
import tensorflow as tf
from keras import layers
from matplotlib import pyplot as plt

from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.metric import Metric

print(tf.__version__)

from alabamaEncode.core.util.bin_utils import register_bin
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence
from alabamaEncode.scene.scene_detection import scene_detect


def get_complexity(enc: Encoder, c: ChunkObject) -> float:
    _enc = copy.deepcopy(enc)
    _enc.chunk = c
    _enc.speed = 12
    _enc.passes = 1
    _enc.rate_distribution = EncoderRateDistribution.CQ
    _enc.crf = 16
    _enc.threads = 1
    _enc.grain_synth = 0
    _enc.output_path = (
        f"/tmp/{c.chunk_index}_complexity{_enc.get_chunk_file_extension()}"
    )
    stats: EncodeStats = _enc.run()
    formula = log(stats.bitrate)
    # self.config.log(
    #     f"[{c.chunk_index}] complexity: {formula:.2f} in {stats.time_encoding}s"
    # )
    os.remove(_enc.output_path)
    return c.chunk_index, formula


def generate_stat_from_chunk(current_chunk: ChunkObject):
    cache_file_name = os.path.join(env, f"{current_chunk.chunk_index}.pkl")

    if os.path.exists(cache_file_name):
        with open(cache_file_name, "rb") as f:
            return pickle.load(f)

    # current_chunk = test_clips[0]
    motion = Ffmpeg.get_vmaf_motion(current_chunk)
    enc = EncoderSvt()
    enc.chunk = current_chunk
    enc.chunk = current_chunk
    enc.chunk.path = current_chunk.path
    enc.video_filters = current_chunk.video_filters
    complexity = get_complexity(enc, current_chunk)
    enc.speed = 4
    enc.passes = 1
    enc.threads = 2
    enc.temp_folder = env

    local_stats = []
    for crf in range(lower_crf, upper_crf, 2):
        enc.crf = crf
        enc.output_path = os.path.join(
            env,
            (
                f"{os.path.basename(current_chunk.chunk_path)}_"
                f"{crf}{enc.get_chunk_file_extension()}"
            ),
        )
        if os.path.exists(enc.output_path):
            os.remove(enc.output_path)
        stat = enc.run(metric_to_calculate=Metric.VMAF)
        stat.basename = [crf, motion, complexity]
        print(
            f"{current_chunk.log_prefix()}VMAF: {stat.vmaf}, motion: {motion}, complexity: {complexity} crf: {crf}"
        )
        stat.version = current_chunk.chunk_index
        local_stats.append(stat)
        os.remove(enc.output_path)

    vmaf_at_32 = [s.vmaf for s in local_stats if s.basename[0] == 32][0]
    for stat in local_stats:
        stat.basename.append(vmaf_at_32)

    with open(cache_file_name, "wb") as f:
        pickle.dump(local_stats, f)
    if not os.path.exists(cache_file_name):
        raise Exception("Failed to save cache file")

    return local_stats


def get_chunks_of_file(path, video_filters):
    scenes: ChunkSequence = scene_detect(
        input_file=path, cache_file_path=f"{env}/sceneCache_{os.path.basename(path)}.pt"
    )

    for c in scenes.chunks:
        c.video_filters = video_filters

    return scenes.chunks


def get_scenes():
    analyzed_chunks = []

    # test_files = [
    #     "/mnt/data/objective-1-fast/ducks_take_off_1080p50_60f.y4m",
    #     "/mnt/data/objective-1-fast/aspen_1080p_60f.y4m",
    #     "/mnt/data/objective-1-fast/rush_hour_1080p25_60f.y4m",
    #     "/mnt/data/objective-1-fast/touchdown_pass_1080p_60f.y4m",
    #     "/mnt/data/objective-1-fast/KristenAndSara_1280x720_60f.y4m",
    #     "/mnt/data/objective-1-fast/vidyo1_720p_60fps_60f.y4m",
    #     "/mnt/data/objective-1-fast/vidyo4_720p_60fps_60f.y4m",
    #     "/mnt/data/objective-1-fast/gipsrestat720p_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_DrivingPOV_1280x720_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/blue_sky_360p_60f.y4m",
    #     "/mnt/data/objective-1-fast/shields_640x360_60f.y4m",
    #     "/mnt/data/objective-1-fast/speed_bag_640x360_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_Aerial_1920x1080_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_Boat_1920x1080_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_Crosswalk_1920x1080_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_FoodMarket_1920x1080_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_PierSeaside_1920x1080_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_SquareAndTimelapse_1920x1080_60fps_8bit_420_60f.y4m",
    #     "/mnt/data/objective-1-fast/Netflix_TunnelFlag_1920x1080_60fps_8bit_420_60f.y4m",
    # ]
    #
    # for i, f in enumerate(test_files):
    #     analyzed_chunks += get_chunks_of_file(f, "")

    analyzed_chunks += get_chunks_of_file(
        "/home/kokoniara/coraline_sc.mkv", f"{Ffmpeg.get_tonemap_vf()}"
    )

    analyzed_chunks += get_chunks_of_file(
        "/home/kokoniara/ep3_halo_test.mkv",
        f"crop=3840:1920:0:120,scale=1920:-2,{Ffmpeg.get_tonemap_vf()}",
    )

    analyzed_chunks += get_chunks_of_file("/mnt/data/liveaction_bright.mkv", "")

    analyzed_chunks += get_chunks_of_file(
        "/mnt/data/liveAction_normal.mp4", "crop=3808:1744:28:208,scale=1920:-2"
    )

    analyzed_chunks += get_chunks_of_file(
        "/home/kokoniara/howlscastle_test.mkv" "crop=1920:1024:0:28"
    )

    for i, c in enumerate(analyzed_chunks):
        c.chunk_path = os.path.join(env, f"{i}.ivf")
        c.chunk_index = i

    return analyzed_chunks


if __name__ == "__main__":
    env = "./crf_vmaf_relation"
    env = os.path.abspath(env)
    if not os.path.exists(env):
        os.mkdir(env)

    analyzed_chunks = get_scenes()

    register_bin(
        "SvtAv1EncApp", "/home/kokoniara/dev/SVT-FASTER/Bin/Release/SvtAv1EncApp"
    )

    lower_crf = 18
    upper_crf = 55

    stats = []

    crfs = range(lower_crf, upper_crf, 2)

    stats_file = os.path.join(env, "stats.pkl")
    if os.path.exists(stats_file):
        with open(stats_file, "rb") as f:
            stats = pickle.load(f)
    else:
        with Executor(max_workers=3) as ex:
            futures = {
                ex.submit(generate_stat_from_chunk, current_chunk): current_chunk
                for current_chunk in analyzed_chunks
            }
            for future in concurrent.futures.as_completed(futures):
                chunk = futures[future]
                try:
                    data = future.result()
                except Exception as exc:
                    print(f"Generated an exception: {exc}")
                else:
                    stats += data

        with open(stats_file, "wb") as f:
            pickle.dump(stats, f)

    stats_by_version = {}
    for stat in stats:
        # if stat version matches a version in the dict, append to that list, else create a new list
        if stat.version in stats_by_version:
            stats_by_version[stat.version].append(stat)
        else:
            stats_by_version[stat.version] = [stat]

    # since crf points are two apart, do interpolation of crf and vmaf and create in-between points
    for version in stats_by_version:
        stats_by_version[version] = sorted(
            stats_by_version[version], key=lambda s: s.basename[0]
        )
        new_stats = []
        for i, stat in enumerate(stats_by_version[version]):
            # first stat is always the same
            if i == 0:
                new_stats.append(stat)
                continue

            # we get the prev stat and then create a interpolated between the curr and last
            prev_stat = stats_by_version[version][i - 1]
            curr_stat = stat
            interpolated_stat = copy.deepcopy(curr_stat)
            interpolated_stat.basename[0] = prev_stat.basename[0] + 1
            interpolated_stat.vmaf = (
                prev_stat.vmaf + curr_stat.vmaf
            ) / 2  # average the vmaf
            new_stats.append(interpolated_stat)
            new_stats.append(curr_stat)

        stats_by_version[version] = new_stats

    train_samples = []  # [[crf at vmaf 96], [motion, complexity]]
    for version in stats_by_version:
        crf_of_vmaf96 = 0
        closest_vmaf = 0
        # search for the crf that is the closest to vmaf 96
        for stat in stats_by_version[version]:
            if abs(stat.vmaf - 96) < abs(closest_vmaf - 96):
                closest_vmaf = stat.vmaf
                crf_of_vmaf96 = stat.basename[0]

        train_samples.append(
            [
                [crf_of_vmaf96],
                [
                    stats_by_version[version][0].basename[1],  # motion
                    stats_by_version[version][0].basename[2],  # complexity
                    # stats_by_version[version][0].basename[3],  # ref
                ],
            ]
        )

    # y is the crf at vmaf 96, x is the motion and complexity
    x = np.array([s[1] for s in train_samples])
    y = np.array([s[0] for s in train_samples])

    print("Size of x: ", x.shape)
    print("Size of y: ", y.shape)

    # (
    #     x_train,
    #     x_test,
    #     y_train,
    #     y_test,
    # ) = train_test_split(x, y, test_size=0.1, random_state=42)
    x_train = x
    y_train = y

    trained_model_path = os.path.join(env, "latest.keras")

    if not os.path.exists(trained_model_path):
        normalisation_layer = layers.Normalization(
            input_shape=[
                x_train.shape[1],
            ]
        )
        normalisation_layer.adapt(x_train)

        # Build a neural network model
        model = tf.keras.Sequential(
            [
                normalisation_layer,
                layers.Dense(64, activation="relu"),
                layers.Dense(64, activation="relu"),
                keras.layers.Dense(1),
            ]
        )

        # Compile the model
        model.compile(optimizer="adam", loss="mean_absolute_error")

        model.summary()

        # Train the model
        history = model.fit(
            x_train,
            y_train,
            epochs=250,
            validation_split=0.2,
        )

        plt.plot(history.history["loss"], label="loss")
        plt.plot(history.history["val_loss"], label="val_loss")
        plt.xlabel("Epoch")
        plt.ylabel("Error [MPG]")
        plt.legend()
        plt.grid(True)
        plt.show()

        model.save(trained_model_path)

        model = keras.models.load_model(trained_model_path)

    else:
        model = keras.models.load_model(trained_model_path)

    # for every scene print the real crf at vmaf 96 and the predicted crf at vmaf 96
    for version in stats_by_version:
        crf_of_vmaf96 = 0
        closest_vmaf = 0
        # search for the crf that is the closest to vmaf 96
        for stat in stats_by_version[version]:
            if abs(stat.vmaf - 96) < abs(closest_vmaf - 96):
                closest_vmaf = stat.vmaf
                crf_of_vmaf96 = stat.basename[0]

        predicted_crf_of_vmaf96 = model.predict(
            [
                [
                    stats_by_version[version][0].basename[1],  # motion
                    stats_by_version[version][0].basename[2],  # complexity
                    # stats_by_version[version][0].basename[3],  # ref
                ]
            ],
            verbose=0,
        )[0][0]

        predicted_crf_of_vmaf96 = int(predicted_crf_of_vmaf96)

        print(
            f"{version} real: {crf_of_vmaf96} predicted: {predicted_crf_of_vmaf96} "
            f"error: {abs(predicted_crf_of_vmaf96 - crf_of_vmaf96)}%"
        )

    quit()

    # old code

    plot_dir = os.path.join(env, "plots")
    if not os.path.exists(plot_dir):
        os.mkdir(plot_dir)

    plots = []
    print(
        "real ideal crf -> resulting vmaf; predicted ideal crf -> resulting vmaf from real data; error %"
    )
    # for each scene plot "crf vs vmaf" with real data vs predicted data, unscaling the predicted data
    for chunk in analyzed_chunks:
        x_crf_of_current_chunk = [
            s.basename[0]
            for s in stats
            if s.version == chunk.path or s.version == chunk.chunk_index
        ]
        x_motion_of_current_chunk = [
            s.basename[1]
            for s in stats
            if s.version == chunk.path or s.version == chunk.chunk_index
        ]
        x_complexity_of_current_chunk = [
            s.basename[2]
            for s in stats
            if s.version == chunk.path or s.version == chunk.chunk_index
        ]
        x_reference_of_current_chunk = [
            s.basename[3]
            for s in stats
            if s.version == chunk.path or s.version == chunk.chunk_index
        ]

        y_of_current_chunk = [
            s.vmaf
            for s in stats
            if s.version == chunk.path or s.version == chunk.chunk_index
        ]

        predicted_scaled_vmaf = []
        for crf, motion, complexity, refrence in zip(
            x_crf_of_current_chunk,
            x_motion_of_current_chunk,
            x_complexity_of_current_chunk,
            x_reference_of_current_chunk,
        ):
            predicted_vmaf = (
                model.predict(
                    [
                        [
                            # crf,
                            motion,
                            complexity,
                            refrence,
                        ]
                    ],
                    verbose=0,
                )[0][0]
                * 100
            )
            predicted_scaled_vmaf.append(predicted_vmaf)

        # Unscale predicted VMAF
        predicted_vmaf = predicted_scaled_vmaf

        def test_against_val(target_value):
            closest_crf_predicted = -1
            closest_vmaf_perdicted = float("inf")
            closest_crf_real = -1
            closest_vmaf_real = float("inf")
            for crf, predicted, real in zip(
                x_crf_of_current_chunk, predicted_vmaf, y_of_current_chunk
            ):
                if abs(predicted - target_value) < abs(
                    closest_vmaf_perdicted - target_value
                ):
                    closest_vmaf_perdicted = predicted
                    closest_crf_predicted = crf
                if abs(real - target_value) < abs(closest_vmaf_real - target_value):
                    closest_vmaf_real = real
                    closest_crf_real = crf

            # within real values find the vmaf value of the closest predicted crf
            pedicted_crf_real_vmaf_value = -1
            for crf, real in zip(x_crf_of_current_chunk, y_of_current_chunk):
                if crf == closest_crf_predicted:
                    pedicted_crf_real_vmaf_value = real
                    break

            # print(
            #     f"{os.path.basename(chunk.path)} Closest crf to vmaf {target_value} is {closest_crf_predicted} (predicted) "
            #     f"and {closest_crf_real} (real), the real vmaf at {closest_crf_predicted} is {pedicted_crf_real_vmaf_value}"
            # )

            is_within_1_of_target = (
                abs(pedicted_crf_real_vmaf_value - target_value) <= 0.5
            )

            print(
                f"{os.path.basename(chunk.path)} {chunk.chunk_index}real: Crf {closest_crf_real} -> {closest_vmaf_real} VMAF,"
                f" predicted: Crf {closest_crf_predicted} -> {pedicted_crf_real_vmaf_value} VMAF;"
                f" within target {'✅' if is_within_1_of_target else '❌'}"
            )

        test_against_val(96)
        test_against_val(94)

        # Plot real vs predicted VMAF
        plt.plot(x_crf_of_current_chunk, y_of_current_chunk, label="Real VMAF")
        plt.plot(x_crf_of_current_chunk, predicted_vmaf, label="Predicted VMAF")
        plt.xlabel("CRF")
        plt.ylabel("VMAF")
        # plt.title(f"{os.path.basename(chunk.path)}")
        plt.title(f"{chunk.chunk_index}")
        plt.legend()
        # plt.show()
        # save the plot to plot with random name
        plot_path = os.path.join(plot_dir, f"{random.randint(0, 1000000)}.png")
        plt.savefig(plot_path)
        plots.append(plot_path)

        plt.clf()

    # create mosaic of plots
    mosaic = os.path.join(env, "mosaic.png")
    os.system(f"montage {' '.join(plots)} -geometry +0+0 {mosaic}")
    print(f"Mosaic of plots saved to {mosaic}")
    for plot in plots:
        os.remove(plot)
