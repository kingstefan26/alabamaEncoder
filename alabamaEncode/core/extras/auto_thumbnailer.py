import hashlib
import json
import multiprocessing
import os

import cv2
import numpy as np
import scipy
from skimage.metrics import structural_similarity as ssim
from tqdm import tqdm

from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.bin_utils import (
    get_binary,
    check_ffmpeg_libraries,
    check_bin,
)
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.get_yuv_stream import get_yuv_frame_stream
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject


def calculate_saliency_score(image):
    # Compute the saliency map
    (success, saliencyMap) = (
        cv2.saliency.StaticSaliencySpectralResidual_create().computeSaliency(image)
    )

    # Check for computation errors
    if not success:
        return 0

    # Convert the saliency map to a NumPy array
    saliencyMap = saliencyMap.astype("float32")

    # Calculate the average saliency score
    average_score = cv2.mean(saliencyMap)[0]

    return average_score


def calculate_rule_of_thirds(image, gray):
    height, width, _ = image.shape
    thirds_x = [width // 3, 2 * width // 3]
    thirds_y = [height // 3, 2 * height // 3]

    _, thresholded = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    key_points = []
    contours, _ = cv2.findContours(
        thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for contour in contours:
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            key_points.append((cX, cY))

    third_score = 0
    for cX, cY in key_points:
        if any(abs(cX - tx) <= width // 20 for tx in thirds_x) and any(
            abs(cY - ty) <= height // 20 for ty in thirds_y
        ):
            third_score += 1

    return third_score / len(key_points) if key_points else 0


def compute_shot_symmetry_score(gray):

    # Split the image into left and right halves
    height, width = gray.shape
    left_half = gray[:, : width // 2]
    right_half = gray[:, width // 2 :]

    # Flip the right half horizontally for comparison
    right_half_flipped = cv2.flip(right_half, 1)

    # Compute the SSIM between the left half and flipped right half
    symmetry_score, _ = ssim(left_half, right_half_flipped, full=True)

    return symmetry_score


def compute_depth_of_field_score(gray):

    # Divide the image into regions (e.g., top, middle, bottom)
    height, width = gray.shape
    regions = [
        gray[: height // 3, :],
        gray[height // 3 : 2 * height // 3, :],
        gray[2 * height // 3 :, :],
    ]

    # Calculate the variance of the Laplacian for each region
    laplacian_vars = [cv2.Laplacian(region, cv2.CV_64F).var() for region in regions]

    # Calculate the standard deviation of the variances
    std_dev_laplacian = np.std(laplacian_vars)

    # Normalize the score (higher score indicates more variation in focus, hence shallower depth of field)
    dof_score = std_dev_laplacian / max(laplacian_vars)

    return dof_score


def face_score(frame) -> float:
    # detect faces, their expressions, and give it a float score
    return 0


def process_frame_worker(yuv_frame_buffer, h, w, count, calc_face=False):
    frame = np.frombuffer(yuv_frame_buffer, dtype=np.uint8).reshape((h * 3 // 2, w))
    frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    aa = {
        "contrast": gray.std(),
        #   "rule_of_thirds": calculate_rule_of_thirds(frame, gray),
        "saliency": calculate_saliency_score(frame),
        "blurriness": cv2.Laplacian(frame, cv2.CV_64F).var(),
        #   "saturation": cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 1].mean(),
        "dof": compute_depth_of_field_score(gray),
        #   "symmetry": compute_shot_symmetry_score(gray),
        "index": count,
    }
    if calc_face:
        aa["face_score"] = face_score(frame)
    return aa


class AutoThumbnailer:
    def __init__(self):
        self.pbar = None

        self.frame_data = []
        self.pool = multiprocessing.Pool(6)
        self.calc_face = False

    def generate_previews(self, input_file: str, output_folder: str):
        chunk = ChunkObject(path=input_file)

        random_part = hashlib.sha1(input_file.encode("utf-8")).hexdigest()[:5]

        frame_data_path = f"{output_folder}/thumbnail_frame_data_{random_part}.json"

        try:
            if os.path.exists(frame_data_path):
                with open(frame_data_path, "r") as f:
                    self.frame_data = json.load(f)
                    print(f"Loaded {len(self.frame_data)} frames from cache")
        except:
            pass

        if len(self.frame_data) <= 0:
            total_length = Ffmpeg.get_frame_count(PathAlabama(chunk.path))
            self.pbar = tqdm(
                total=total_length, desc="Gathering thumbnail data", unit="frame"
            )

            get_yuv_frame_stream(
                chunk,
                frame_callback=self.process_frame,
                vf="\"scale=-2:min'(720,ih)':force_original_aspect_ratio=decrease\"",
            )

            # await all the tasks in the pool to be finished
            self.pool.close()
            self.pool.join()

            with open(frame_data_path, "w") as f:
                json.dump(self.frame_data, f)

            self.pbar.close()

            print(f"Processed {len(self.frame_data)} frames")

        if len(self.frame_data) == 0:
            raise Exception("No frames were processed")

        features_to_calc = [
            "blurriness",
            "saliency",
            # 'rule_of_thirds',
            "contrast",
            # 'saturation',
            "dof",
            # 'symmetry'
        ]

        if self.calc_face:
            features_to_calc.append("face_score")

        best_frames = self.get_top_frames(
            self.frame_data,
            num_peaks=9,
            feature_names=features_to_calc,
        )

        has_placebo = check_ffmpeg_libraries("libplacebo")
        has_jpegli = check_bin("cjpeg")
        for i, best_frame in tqdm(
            enumerate(best_frames), desc="Saving best frames", total=len(best_frames)
        ):
            chunk = ChunkObject(
                first_frame_index=best_frame,
                last_frame_index=best_frame + 1,
                path=input_file,
            )
            if has_placebo and has_jpegli:
                command = f"{get_binary('ffmpeg')} -init_hw_device vulkan -y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 -vf 'hwupload,libplacebo=minimum_peak=2:percentile=99.6:tonemapping=spline:colorspace=bt709:color_primaries=bt709:gamut_mode=perceptual:color_trc=bt709:range=tv:gamma=1:format=yuv420p,hwdownload,format=yuv420p' -c:v png -f image2pipe - | {get_binary('cjpeg')} -q 95 -tune-psnr -optimize -progressive > \"{output_folder}/{i}.jpg\""
            elif has_placebo:
                command = f"{get_binary('ffmpeg')} -init_hw_device vulkan -y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 -vf 'hwupload,libplacebo=minimum_peak=2:percentile=99.6:tonemapping=spline:colorspace=bt709:color_primaries=bt709:gamut_mode=perceptual:color_trc=bt709:range=tv:gamma=1:format=yuv420p,hwdownload,format=yuv420p' \"{output_folder}/{i}.png\""
            else:
                command = f"{get_binary('ffmpeg')} -y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 \"{output_folder}/{i}.png\""
            run_cli(command).verify()

    def process_frame(self, yuv_frame):
        self.pool.apply_async(
            process_frame_worker,
            args=(
                yuv_frame.buffer,
                yuv_frame.headers["H"],
                yuv_frame.headers["W"],
                yuv_frame.count,
                self.calc_face,
            ),
            callback=self.collect_result,
        )

    def collect_result(self, result):
        self.frame_data.append(result)
        self.pbar.update()

    # def process_frame(self, yuv_frame):
    #     frame = np.frombuffer(yuv_frame.buffer, dtype=np.uint8).reshape((yuv_frame.headers['H'] * 3 // 2, yuv_frame.headers['W']))
    #     frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)
    #     gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #
    #     self.frame_data.append({
    #         "blurriness": cv2.Laplacian(frame, cv2.CV_64F).var(),
    #         "contrast": gray.std(),
    #         "saliency": calculate_saliency_score(frame),
    #         "index": yuv_frame.count,
    #         "rule_of_thirds": calculate_rule_of_thirds(frame, gray)
    #     })
    #     self.pbar.update()

    def normalize_and_combine(self, frame_data, feature_names):
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

        # if any of the values contain nan's kick them out
        # normalized_features = {k: v for k, v in normalized_features.items() if not np.isnan(v).any()}

        # change any nans in the data into 0's
        for feature, values in normalized_features.items():
            normalized_features[feature] = np.nan_to_num(values)

        # Combine the normalized scores into a single score
        combined_score = np.zeros_like(list(normalized_features.values())[0])
        for feature, normalized_values in normalized_features.items():
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

            combined_score += normalized_values
        return combined_score

    # Step 2: Smooth the data to highlight peaks
    def smooth_data(self, combined_score):
        # print pre and post smoothing on top of eathcother in color
        # smoothed_score = scipy.signal.savgol_filter(combined_score, window_length=20, polyorder=2)
        # smoothed_score = scipy.ndimage.gaussian_filter1d(combined_score, sigma=100)
        # alt mode where you increate the smoothing factor based on lenght up to a point
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

    # Step 3: Find peaks in the smoothed data
    def find_peaks(self, smoothed_score):
        peaks, _ = scipy.signal.find_peaks(
            smoothed_score, distance=len(smoothed_score) // 20
        )  # Adjust distance for peak spacing

        # print the data with peeks overlayed
        # import matplotlib.pyplot as plt
        #
        # plt.plot(smoothed_score, label="Smoothed Score")
        # plt.plot(peaks, smoothed_score[peaks], "x", label="Peaks")
        # plt.legend()
        # plt.show()

        return peaks

    # Step 4: Select evenly spaced peaks or fallback to highest scores
    def select_evenly_spaced_peaks(self, peaks, num_peaks, combined_score):

        if not len(peaks) >= num_peaks:
            print(f"Detection only found {len(peaks)} good candidates, using them")
            return peaks
        else:
            step = len(peaks) // num_peaks
            evenly_spaced_peaks = peaks[::step][:num_peaks]
        # if len(peaks) >= num_peaks:
        #     step = len(peaks) // num_peaks
        #     evenly_spaced_peaks = peaks[::step][:num_peaks]
        # else:
        #     # Fallback: select frames with the highest combined scores
        #     top_indices = np.argsort(-combined_score)[:num_peaks]
        #     evenly_spaced_peaks = sorted(top_indices)
        return evenly_spaced_peaks

    # Main function to get top frame indices
    def get_top_frames(self, frame_data, feature_names, num_peaks=5):
        print("Processing frame data...")
        combined_score = self.normalize_and_combine(frame_data, feature_names)
        smoothed_score = self.smooth_data(combined_score)
        peaks = self.find_peaks(smoothed_score)
        selected_peaks = self.select_evenly_spaced_peaks(
            peaks, num_peaks, combined_score
        )
        selected_indices = [frame_data[peak]["index"] for peak in selected_peaks]

        print(f"Selected frames: {selected_indices}")
        return selected_indices


if __name__ == "__main__":
    AutoThumbnailer().generate_previews(
        "/home/kokoniara/Downloads/I Bought 6 PC “Speed Up” Tools to See if They Work [-G-DByczbWA].webm",
        ".",
    )
    # AutoThumbnailer().generate_previews(
    #     "/home/kokoniara/showsEncode/Silo (2023)/s1/e9/Silo.2023.S01E09.OPUS.AV1.1080p.webm",
    #     ".",
    # )
