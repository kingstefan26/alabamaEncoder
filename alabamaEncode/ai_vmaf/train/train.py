import json
import os
import pickle

import keras
from keras.src.layers import Dense, LSTM, MaxPooling1D, Normalization
from keras_tuner import BayesianOptimization
from sklearn.model_selection import train_test_split
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map

from alabamaEncode.ai_vmaf.aom_firstpass import aom_extract_firstpass_data
from alabamaEncode.core.bin_utils import register_bin
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence
from alabamaEncode.scene.split import get_video_scene_list_skinny


def get_chunks_of_file(path, env, video_filters=""):
    scenes: ChunkSequence = get_video_scene_list_skinny(
        input_file=path, cache_file_path=f"{env}/sceneCache_{os.path.basename(path)}.pt"
    )

    for c in scenes.chunks:
        c.video_filters = video_filters

    return scenes.chunks


def get_chunks_for_analysis(env):
    analyzed_chunks = []

    # analyzed_chunks += get_chunks_of_file("test.mp4", "crop=etc", env=env)
    # ...

    # analyzed_chunks += get_chunks_of_file(
    #     "/mnt/data/objective-1-fast/Netflix_Aerial_1920x1080_60fps_8bit_420_60f.y4m",
    #     env=env,
    # )
    #
    # analyzed_chunks += get_chunks_of_file(
    #     "/mnt/data/objective-1-fast/Netflix_Crosswalk_1920x1080_60fps_8bit_420_60f.y4m",
    #     env=env,
    # )

    analyzed_chunks += get_chunks_of_file(
        "/home/kokoniara/coraline_sc.mkv",
        env=env,
        video_filters=f"scale=1920:-2,{Ffmpeg.get_tonemap_vf()}",
    )

    # analyzed_chunks += get_chunks_of_file(
    #     "/home/kokoniara/ep3_halo_test.mkv",
    #     env=env,
    #     video_filters=f"crop=3840:1920:0:120,scale=1920:-2,{Ffmpeg.get_tonemap_vf()}",
    # )

    analyzed_chunks += get_chunks_of_file(
        "/mnt/data/downloads/Halo.S01.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP/Halo.S01E05.Reckoning.2160p.UHD"
        ".BluRay.Remux.HDR.DV.HEVC.Atmos-PmP.mkv",
        env=env,
        video_filters=f"crop=3840:1920:0:120,scale=1920:-2,{Ffmpeg.get_tonemap_vf()}",
    )

    analyzed_chunks += get_chunks_of_file("/mnt/data/liveaction_bright.mkv", env)[:5]

    analyzed_chunks += get_chunks_of_file(
        "/mnt/data/liveAction_normal.mp4",
        env=env,
        video_filters="crop=3808:1744:28:208,scale=1920:-2",
    )

    analyzed_chunks += get_chunks_of_file(
        "/home/kokoniara/howlscastle_test.mkv",
        env=env,
        video_filters="crop=1920:1024:0:28",
    )

    analyzed_chunks += get_chunks_of_file(
        "/home/kokoniara/ahs_s12_e05_cliptest.mp4", env=env
    )

    analyzed_chunks += get_chunks_of_file(
        "/mnt/data/liveAction_highMotion.mkv",
        env=env,
        video_filters="crop=1920:800:0:140",
    )

    analyzed_chunks += get_chunks_of_file(
        "/home/kokoniara/lesssons_in_methistry.mkv",
        env=env,
        video_filters=f"scale=1920:-2,{Ffmpeg.get_tonemap_vf()}",
    )

    for i, c in enumerate(analyzed_chunks):
        c.chunk_path = os.path.join(env, f"{i}.ivf")
        c.chunk_index = i

    return analyzed_chunks


def process_chunk(chunk):
    cache_file_name = chunk.chunk_path + ".cache"

    if os.path.exists(cache_file_name):
        with open(cache_file_name, "rb") as f:
            stats = pickle.load(f)
            tqdm.write(f"Found & Loaded cache stat for {chunk.chunk_path}")
            return stats
    else:
        tqdm.write(f"[{chunk.chunk_path}] Cache not found, ignoring for now")
        return None
        enc = EncoderSvt()
        # enc = EncoderX264()
        enc.chunk = chunk
        if hasattr(chunk, "video_filters") is False or chunk.video_filters is None:
            chunk.video_filters = ""
        enc.video_filters = chunk.video_filters

        enc.speed = 5
        enc.passes = 1
        enc.threads = 2
        enc.rate_distribution = EncoderRateDistribution.CQ

        local_stats = {}
        # for crf in range(18, 55, 2):
        for crf in [
            12,
            15,
            17,
            19,
            21,
            23,
            25,
            27,
            29,
            31,
            34,
            37,
            40,
            43,
            46,
            49,
            52,
            55,
            58,
        ]:
            enc.crf = crf
            enc.output_path = os.path.join(
                os.path.dirname(chunk.chunk_path),
                f"{crf}_{chunk.chunk_index}{enc.get_chunk_file_extension()}",
            )
            local_stats[str(crf)] = enc.run(calculate_vmaf=True).__dict__()
            if os.path.exists(enc.output_path):
                os.remove(enc.output_path)

        features = Ffmpeg.get_content_features(chunk, vf=chunk.video_filters)

        aom_features = aom_extract_firstpass_data(chunk, vf=chunk.video_filters)

        stats = {
            "features": features,
            "chunk_stats": local_stats,
            "aom_features": aom_features,
        }

        with open(cache_file_name, "wb") as f:
            pickle.dump(stats, f)
        if not os.path.exists(cache_file_name):
            raise Exception("Failed to save cache file")

    return stats


def process_chunks(env, chunks, max_workers=4):
    stats_file = os.path.join(env, "stats.pkl")
    stats = []

    if os.path.exists(stats_file):
        with open(stats_file, "rb") as f:
            return pickle.load(f)

    for item in process_map(
        process_chunk, chunks, max_workers=max_workers, chunksize=1
    ):
        if item is not None:
            stats.append(item)

    with open(stats_file, "wb") as f:
        pickle.dump(stats, f)

    return stats


def prepare_data(stats):
    features_list = []
    labels_list = []

    for chunk in stats:
        crf_values = list(
            chunk["chunk_stats"].keys()
        )  # Get the list of CRF values in the chunk

        features_chunk = []
        for frame in chunk["features"]:
            frame_features = [
                float(value) for value in chunk["features"][frame].values()
            ]
            features_chunk.append(frame_features)
        for crf in crf_values:
            vmaf_at_crf = chunk["chunk_stats"][crf]["vmaf"]
            print(f"VMAF at crf {crf}: {vmaf_at_crf}")
            features_with_vmaf = features_chunk.copy()
            for frame in features_with_vmaf:
                frame.append(float(vmaf_at_crf))
            features_list.append(features_with_vmaf)

            labels = [0] * len(crf_values)
            # 1 at the index of the crf value
            labels[crf_values.index(crf)] = 1
            labels_list.append(labels)

    return features_list, labels_list


def process_chunk_test():
    register_bin("SvtAv1EncApp", "/home/kokoniara/.local/opt/SvtAv1EncApp")
    test_chunk = ChunkObject(
        path="/mnt/data/objective-1-fast/Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f.y4m"
    )
    env = os.path.abspath("./ai_feature_extract_test")
    if not os.path.exists(env):
        os.mkdir(env)

    test_chunk.chunk_path = os.path.join(env, "test.ivf")

    stats = process_chunk(test_chunk)
    print(stats)


def process_chunks_test():
    register_bin("SvtAv1EncApp", "/home/kokoniara/.local/opt/SvtAv1EncApp")
    env = os.path.abspath("./ai_feature_extract_test")
    if not os.path.exists(env):
        os.mkdir(env)

    chunks = get_chunks_for_analysis(env)
    stats = process_chunks(env, chunks)
    print(json.dumps(stats, indent=4))


def test_nn_impl():
    register_bin("SvtAv1EncApp", "/home/kokoniara/.local/opt/SvtAv1EncApp")
    env = os.path.abspath("./ai_feature_extract_test")
    if not os.path.exists(env):
        os.mkdir(env)

    # getting data
    chunks = get_chunks_for_analysis(env)
    print(f"Starting processing of {len(chunks)} chunks")
    stats = process_chunks(env, chunks)

    # preparing data
    features, labels = prepare_data(stats)

    print(f"Using {len(features)} chunks for training")

    # Turn into numpy arrays
    # features = np.array(features)
    # labels = np.array(labels)
    #
    # labels /= 100

    labels = [x / 100 for x in labels]

    # training model
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2)

    normalization_layer = Normalization(
        input_shape=(len(features[0]), len(features[0][0])), name="frame_features"
    )

    normalization_layer.adapt(X_train)

    # Define the model building function for keras-tuner
    def build_model_lstm(hp):
        model = keras.Sequential()
        num_layers = hp.Int("num_layers", 1, 4)

        model.add(normalization_layer)
        for layer in range(num_layers):
            if layer < num_layers - 1:
                model.add(
                    LSTM(
                        units=hp.Int(
                            f"units_{layer}", min_value=32, max_value=480, step=32
                        ),
                        return_sequences=True,
                    )
                )
            else:
                model.add(
                    LSTM(
                        units=hp.Int(
                            "units_last", min_value=32, max_value=480, step=32
                        ),
                    )
                )

        model.add(Dense(1, activation="linear", name="predicted_crf"))
        model.compile(optimizer="adam", loss="mse")
        return model

    def build_model_dense(hp):
        model = keras.Sequential()
        model.add(
            MaxPooling1D(
                pool_size=hp.Int("pool_size", min_value=2, max_value=10, step=2),
                input_shape=(X_train.shape[1], X_train.shape[2]),
            )
        )
        for layer in range(hp.Int("num_layers", 1, 4)):
            model.add(
                Dense(
                    units=hp.Int("units", min_value=32, max_value=512, step=32),
                    activation="relu",
                )
            )

        model.add(Dense(1, activation="linear", name="predicted_crf"))

        model.compile(optimizer="adam", loss="mse")
        return model

    # Set up the tuner
    tuner = BayesianOptimization(
        build_model_lstm,
        # build_model_dense,
        objective="val_loss",
        max_trials=10,
    )

    # Perform the hyperparameter search
    # tuner.search(X_train, y_train, epochs=5, validation_data=(X_test, y_test))
    tuner.search(
        X_train,
        y_train,
        epochs=100,
        validation_data=(X_test, y_test),
        callbacks=[
            keras.callbacks.EarlyStopping(monitor="loss", patience=4),
            keras.callbacks.TensorBoard("/tmp/tb_logs"),
        ],
    )

    # Get the best model
    best_model = tuner.get_best_models()[0]

    # plot the learning curve of the best model

    # Evaluate the best model on the test set
    loss = best_model.evaluate(X_test, y_test)
    print(f"Test Loss: {loss}")

    # Do a prediction using the best model
    predictions = best_model.predict(X_test)
    print(f"Predicted: {predictions.flatten()}, Actual: {y_test}")

    # for all the chunks fo a prediction and print it
    for data, i in zip(features, range(len(features))):
        prediction = best_model.predict(data.reshape((1, *data.shape)))
        print(f"Chunk {i} predicted crf: {prediction.flatten()} real crf: {labels[i]}")

    # Save the model
    best_model.save(os.path.join(env, "model.keras"))


def test_nn_two():
    register_bin("SvtAv1EncApp", "/home/kokoniara/.local/opt/SvtAv1EncApp")
    env = os.path.abspath("./ai_feature_extract_test")
    if not os.path.exists(env):
        os.mkdir(env)

    # getting data
    chunks = get_chunks_for_analysis(env)
    print(f"Starting processing of {len(chunks)} chunks")
    stats = process_chunks(env, chunks)

    # preparing data
    features, labels = prepare_data(stats)

    # describe data using pd
    import pandas as pd

    df = pd.DataFrame(features)
    print(df)
    print("Features shape")
    print(df.shape)

    df = pd.DataFrame(labels)
    print("\nLabels Shape")
    print(df.shape)

    print(f"Using {len(features)} chunks for training")


if __name__ == "__main__":
    # process_chunk_test()
    # process_chunks_test()
    # test_nn_impl()
    test_nn_two()
