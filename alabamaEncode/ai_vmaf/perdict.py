import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import numpy as np
from keras.preprocessing import sequence

from alabamaEncode.core.ffmpeg import Ffmpeg

import keras

model = None


def predict_crf(chunk, vf=""):
    global model
    if model is None:
        model = keras.models.load_model(
            "/home/kokoniara/dev/VideoSplit/alabamaEncode/ai_vmaf/"
            "train/ai_feature_extract_test/model.keras"
        )

    features_dict = Ffmpeg.get_content_features(chunk, vf=vf)

    # do this weird dance to get the data in the right shape

    features = []
    for frame in features_dict:
        frame_features = [float(value) for value in features_dict[frame].values()]
        features.append(frame_features)

    features = np.array([features])

    features = sequence.pad_sequences(
        features, maxlen=232, dtype="float32", padding="post"
    )

    features = features.reshape((1, *features.shape))

    crf = model.predict(features[0], verbose=0)[0][0]

    crf *= 100

    return int(crf)

