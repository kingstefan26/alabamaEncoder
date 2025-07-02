import os
from typing import List, Tuple

import face_recognition
import numpy as np
import scipy

from alabamaEncode.core.extras.autothumbnail.opt import autothumbnailOptions

graph_folder = None


# Step 4: Select evenly spaced peaks or fallback to highest scores
def select_evenly_spaced_peaks(peaks, num_peaks):
    if not len(peaks) >= num_peaks:
        print(f"Detection only found {len(peaks)} good candidates, using them")
        return peaks
    else:
        step = len(peaks) // num_peaks
        evenly_spaced_peaks = peaks[::step][:num_peaks]
    return evenly_spaced_peaks


# Step 3: Find peaks in the smoothed data
def find_peaks(smoothed_score):
    print(smoothed_score)
    peaks, _ = scipy.signal.find_peaks(
        smoothed_score, distance=len(smoothed_score) // 10
    )  # Adjust distance for peak spacing

    # print the data with peeks overlayed
    import matplotlib.pyplot as plt

    plt.clf()
    plt.plot(smoothed_score, label="Smoothed Score")
    plt.plot(peaks, smoothed_score[peaks], "x", label="Peaks")
    plt.legend()
    plt.show()
    plt.savefig(f"{graph_folder}/Smoothed Score.png")

    if len(peaks) <= 1:
        highest = 0
        highest_num = 0
        for i, score in enumerate(smoothed_score):
            if score > highest:
                highest = score
                highest_num = i
        peaks = [highest_num]

    return peaks


# Step 2: Smooth the data to highlight peaks
def smooth_data(combined_score):
    # increate the smoothing factor based on lenght up to a point
    smoothing_factor = min(100, len(combined_score) // 10)
    smoothed_score = scipy.ndimage.gaussian_filter1d(
        combined_score, sigma=smoothing_factor
    )

    # import matplotlib.pyplot as plt
    #
    # plt.plot(combined_score, label="Combined Score")
    # plt.plot(smoothed_score, label="Smoothed Score")
    # plt.legend()
    # plt.show()

    return smoothed_score


def normalize_and_combine(frame_data, feature_names):
    features = {
        feature: np.array([frame[feature] for frame in frame_data])
        for feature in feature_names
    }

    # Normalize each feature to [0, 1]
    normalized_features = {}
    for feature, values in features.items():
        min_val = values.min()
        max_val = values.max()
        if max_val - min_val != 0:  # Avoid division by zero
            normalized_features[feature] = (values - min_val) / (max_val - min_val)
        else:
            normalized_features[feature] = values - min_val

    import matplotlib.pyplot as plt

    # Plot all features using matplotlib.pyplot
    plt.figure(figsize=(12, 8))
    for i, (feature, values) in enumerate(normalized_features.items()):
        plt.subplot(len(feature_names), 1, i + 1)
        plt.plot(values, label=feature)
        plt.title(feature)
        plt.xlabel("Frame Index")
        plt.ylabel("Value")
        plt.legend()

    plt.tight_layout()
    plt.show()
    plt.savefig(f"{graph_folder}/normalised.png")

    # change any nans in the data into 0's
    for feature, values in normalized_features.items():
        normalized_features[feature] = np.nan_to_num(values)

    apply_modifiers = False

    # Combine the normalized scores into a single score
    combined_score = np.zeros_like(list(normalized_features.values())[0])
    for feature, normalized_values in normalized_features.items():
        if apply_modifiers:
            if feature == "contrast":
                normalized_values *= 0.7
            elif feature == "saliency":
                normalized_values *= 1.5
            elif feature == "blurriness":
                normalized_values *= 1.8
            elif feature == "saturation":
                normalized_values *= 0.4
            elif feature == "dof":
                normalized_values *= 0.9
            elif feature == "face_score":
                normalized_values *= 3

        combined_score += normalized_values

    plt.clf()
    plt.plot(combined_score, label="Combined Score")
    plt.legend()
    plt.show()
    plt.savefig(f"{graph_folder}/Combined Score.png")

    return combined_score


def process_face_data(options: autothumbnailOptions, frame_data):
    # the process:
    # calculate the popularity of the current face in the data
    #   cluster all vectors in the 128-dimensional space
    #   for each vector calculate the size of the cluster that its in
    #   get the top ~6 cluster sizes
    #   the score is 1 per each face that is top 6 in cluster sizes
    #
    #
    # give score if top {3} faces appear in frame

    for frame in frame_data:
        if "face_embeddings" in frame:
            print(
                f'frame {frame["index"]} contatins {len(frame["face_embeddings"])} faces'
            )

    face_face_encodings: List[Tuple[int, int, np.array]] = []
    # List[Tuple[frame index, face id, face encoding]]
    # x = []
    face_id_counter = 0
    for frame in frame_data:
        if "face_embeddings" in frame:
            if len(frame["face_embeddings"]) == 0:
                continue
            for fe in frame["face_embeddings"]:
                face_face_encodings.append(
                    [frame["index"], face_id_counter, np.array(fe)]
                )
                face_id_counter += 1
                # x += [fe[50]]

    unique_faces = face_face_encodings
    # loop over, and delete all the ones that match
    i = 0
    while i < len(unique_faces) - 1:
        curr_face = unique_faces[i]
        cur_frame_index, cur_face_id, curr_face = curr_face

        marked_for_deletion = []

        j = i + 1
        while j < len(unique_faces) - 1:
            nx_f = unique_faces[j]
            nx_fi, nx_face_id, nx_face = nx_f

            matches = face_recognition.compare_faces([curr_face], nx_face)
            if any(matches):
                # print(f"face {cur_face_id} & {nx_face_id} match, marking for deletion")
                marked_for_deletion.append(nx_f)

            j += 1

        for for_deletion in marked_for_deletion:
            unique_faces.remove(for_deletion)

        i += 1

    print(
        f"In {len(frame_data)} frames found {len(unique_faces)} unique face encodings"
    )

    # add a fourth parameter, for counting occurrences
    unique_faces = [[x, y, z, 0] for x, y, z in unique_faces]
    unique_faces_encodings_only = [z for x, y, z, i in unique_faces]

    # count occurencess
    for frame in frame_data:
        if "face_embeddings" in frame:
            if len(frame["face_embeddings"]) == 0:
                continue
            for fe in frame["face_embeddings"]:
                fe_nparr = np.array(fe)
                matches = face_recognition.compare_faces(
                    unique_faces_encodings_only, fe_nparr
                )
                for i, match in enumerate(matches):
                    if match:
                        unique_faces[i][3] += 1

    # sort based on frequency
    unique_faces.sort(key=lambda face: face[3], reverse=True)

    for unique_face in unique_faces:
        f_id, face_id, emb, freq = unique_face
        print(f"face id {face_id} was detected {freq} times")

    # get the top 3 faces
    top_unique_faces = unique_faces[:3]
    top_unique_faces_encodings = [z for x, y, z, xx in top_unique_faces]

    for frame in frame_data:
        if "face_embeddings" in frame:
            if len(frame["face_embeddings"]) == 0:
                continue
            for fe in frame["face_embeddings"]:
                matches = face_recognition.compare_faces(
                    top_unique_faces_encodings, np.array(fe)
                )
                for match in matches:
                    if match:
                        frame["face_score"] += 3


def compute_best_candidates(
    frame_data, output_folder, options: autothumbnailOptions, num_peaks=5
):
    global graph_folder
    graph_folder = output_folder + "/graphs/"
    os.makedirs(graph_folder, exist_ok=True)
    feature_names = [
        "blurriness",
        "saliency",
        # 'rule_of_thirds',
        "contrast",
        # 'saturation',
        # "dof",
        # 'symmetry'
    ]

    if options.detect_faces:
        feature_names += ["face_score"]
        process_face_data(options, frame_data)

    print("Processing frame data...")

    combined_score = normalize_and_combine(frame_data, feature_names)
    smoothed_score = smooth_data(combined_score)
    peaks = find_peaks(smoothed_score)
    selected_peaks = select_evenly_spaced_peaks(peaks, num_peaks)
    selected_indices = [frame_data[peak]["index"] for peak in selected_peaks]

    print(f"Selected frames: {selected_indices}")
    return selected_indices
