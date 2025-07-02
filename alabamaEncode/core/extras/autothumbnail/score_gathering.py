import multiprocessing
import os

import cv2
import face_recognition
import numpy as np
import requests
from skimage.metrics import structural_similarity as ssim
from tqdm import tqdm

from alabamaEncode.core.extras.autothumbnail.opt import autothumbnailOptions
from alabamaEncode.core.ffmpeg import Ffmpeg
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


found_face_embeddings = []


def face_score(frame) -> float:
    model_folder = os.path.expanduser("~/.alabamaEncoder/models")
    if not os.path.exists(model_folder):
        os.makedirs(model_folder)
    deploy_path = model_folder + "/deploy.prototxt"
    model_path = model_folder + "/res10_300x300_ssd_iter_140000.caffemodel"
    if not os.path.exists(deploy_path):
        r = requests.get(
            "https://raw.githubusercontent.com/keyurr2/face-detection/refs/heads/master/deploy.prototxt.txt",
            allow_redirects=True,
        )
        open(deploy_path, "wb").write(r.content)
    if not os.path.isfile(model_path):
        r = requests.get(
            "https://raw.githubusercontent.com/keyurr2/face-detection/refs/heads/master/res10_300x300_ssd_iter_140000.caffemodel",
            allow_redirects=True,
        )
        open(model_path, "wb").write(r.content)

    if not hasattr(face_score, "net"):
        face_score.net = cv2.dnn.readNetFromCaffe(deploy_path, model_path)

    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
    face_score.net.setInput(blob)
    detections = face_score.net.forward()

    total_score = 0.0
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:  # Confidence threshold
            box = detections[0, 0, i, 3:7] * np.array(
                [frame.shape[1], frame.shape[0]] * 2
            )
            w = box[2] - box[0]
            h = box[3] - box[1]
            total_score += w * h

    return total_score


def alternative_face_scoring(frame):
    global faces_in_frames
    fe = face_recognition.face_encodings(frame)
    score = min(len(fe), 2)

    return score, [f.tolist() for f in fe]


def process_frame_worker(yuv_frame_buffer, h, w, count):
    frame = np.frombuffer(yuv_frame_buffer, dtype=np.uint8).reshape((h * 3 // 2, w))
    frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_scores = {
        "contrast": gray.std(),
        "saliency": calculate_saliency_score(frame),
        "blurriness": cv2.Laplacian(frame, cv2.CV_64F).var(),
        # "dof": compute_depth_of_field_score(gray),
        "index": count,
        #   "symmetry": compute_shot_symmetry_score(gray),
        #   "rule_of_thirds": calculate_rule_of_thirds(frame, gray),
        #   "saturation": cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 1].mean(),
    }
    # if options.detect_faces:
    #     frame_scores["face_score"] = face_score(frame)

    if options.detect_faces:
        score, embeddings = alternative_face_scoring(frame)
        frame_scores["face_score"] = score
        frame_scores["face_embeddings"] = embeddings

    face_recognition.compare_faces()
    return frame_scores


pool = None
options: autothumbnailOptions = None
frame_data = []
pbar = None


def process_frame(yuv_frame):
    pool.apply_async(
        process_frame_worker,
        args=(
            yuv_frame.buffer,
            yuv_frame.headers["H"],
            yuv_frame.headers["W"],
            yuv_frame.count,
        ),
        callback=collect_result,
    )


def collect_result(result):
    frame_data.append(result)
    pbar.update()


def get_frame_scores(_options: autothumbnailOptions):
    global pbar
    global pool
    global frame_data
    global options
    options = _options
    calc_face = options.detect_faces
    pool = multiprocessing.Pool(6)
    pbar = tqdm(
        total=Ffmpeg.get_frame_count(PathAlabama(options.input_file)),
        desc="Gathering thumbnail data",
        unit="frame",
    )

    get_yuv_frame_stream(
        ChunkObject(path=options.input_file),
        frame_callback=process_frame,
        vf="\"scale=-2:min'(720,ih)':force_original_aspect_ratio=decrease\"",
    )

    # await all the tasks in the pool to be finished
    pool.close()
    pool.join()
    pbar.close()

    print(f"Processed {len(frame_data)} frames")

    return frame_data
