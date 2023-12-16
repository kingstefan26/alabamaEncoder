import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import keras

model = None


def get_crf_for_vmaf(model_path, vmaf_motion, complexity, vmaf_target):
    global model
    if model is None:
        model = keras.models.load_model(model_path)

    return int(model.predict([[vmaf_motion, complexity]], verbose=0)[0][0])


# def get_crf_for_vmaf(model_path, vmaf_motion, complexity, vmaf_target):
#     global model
#     if model is None:
#         model = keras.models.load_model(model_path)
#
#     guesses: List[Tuple[int, float]] = []
#     for crf in range(22, 55):
#         guesses.append((crf, perdict(model, complexity, crf, vmaf_motion)))
#
#     closest_crf = 0
#     closest_vmaf = 0
#     for guess in guesses:
#         if abs(guess[1] - vmaf_target) < abs(closest_vmaf - vmaf_target):
#             closest_vmaf = guess[1]
#             closest_crf = guess[0]
#
#     return closest_crf
#
#
# def perdict(model, compelxity, crf, vmafmotion):
#     result = model.predict([[crf, vmafmotion, compelxity]], verbose=0)[0][0] * 100
#     return result
