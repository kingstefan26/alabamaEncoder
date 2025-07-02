import hashlib
import json
import os

from alabamaEncode.core.extras.autothumbnail.data_processing import (
    compute_best_candidates,
)
from alabamaEncode.core.extras.autothumbnail.final_image_extraction import (
    extract_frames_and_encode,
)
from alabamaEncode.core.extras.autothumbnail.opt import autothumbnailOptions
from alabamaEncode.core.extras.autothumbnail.score_gathering import get_frame_scores


def generate_autothumbnail_previews(
    input_file: str,
    output_folder: str,
    options: autothumbnailOptions = None,
):
    output_folder = output_folder
    if options is None:
        options = autothumbnailOptions()

    options.input_file = input_file
    options.output_folder = output_folder

    random_part = hashlib.sha1(options.input_file.encode()).hexdigest()[:5]

    data_cache_path = f"{options.output_folder}/thumbnail_frame_data_{random_part}.json"

    frame_data = []

    try:
        if os.path.exists(data_cache_path):
            with open(data_cache_path) as f:
                frame_data = json.load(f)
                print(f"Loaded {len(frame_data)} frames from cache")
    except:
        pass

    if len(frame_data) == 0:
        frame_data = get_frame_scores(options)

        with open(data_cache_path, "w") as f:
            json.dump(frame_data, f)

    if len(frame_data) == 0:
        raise Exception("Missing frame data (No frames processed?)")

    best_frames = compute_best_candidates(
        frame_data,
        output_folder,
        options,
        num_peaks=9,
    )

    extract_frames_and_encode(
        best_frames,
        skip_result_image_optimisation=options.skip_result_image_optimisation,
        input_file=options.input_file,
        output_folder=options.output_folder,
    )


if __name__ == "__main__":
    generate_autothumbnail_previews(
        "/home/kokoniara/Downloads/I Bought 6 PC “Speed Up” Tools to See if They Work [-G-DByczbWA].webm",
        ".",
    )
    # AutoThumbnailer().generate_previews(
    #     "/home/kokoniara/showsEncode/Silo (2023)/s1/e9/Silo.2023.S01E09.OPUS.AV1.1080p.webm",
    #     ".",
    # )
