import copy
import json
import os

from scenedetect import detect, AdaptiveDetector

from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


def scene_detect(
    input_file: str,
    cache_file_path: str,
    max_scene_length: int = 10,
    start_offset=-1,
    end_offset=-1,
    override_bad_wrong_cache_path=False,
    static_length=False,
    scene_merge=False,
    static_length_size=30,
) -> ChunkSequence:
    """
    :param static_length_size:  size of static length scenes in seconds
    :param static_length: instead of detection, create static length scenes
    :param override_bad_wrong_cache_path:
    :param start_offset:
    :param end_offset:
    :param input_file: input file
    :param cache_file_path: path that the cache will be saved to
    :param max_scene_length: max scene length in seconds,
     cut the scene in the middle recursively until max_scene_length is reached
    :param scene_merge: merge scenes, so they are at minimum max_scene_length
    :return:
    """
    cache_path_is_valid = cache_file_path is not None and cache_file_path != ""

    seq = ChunkSequence([])
    if cache_path_is_valid and os.path.exists(cache_file_path):
        seq.load_json(open(cache_file_path).read())

        # Ensure input file matches the cached sequence
        if seq.input_file != input_file and not override_bad_wrong_cache_path:
            raise Exception(
                f"Video ({input_file}) != ({seq.input_file}) does not match scene cache ({cache_file_path}),"
                f" please correct this (wrong temp folder?), use --override_bad_wrong_cache_path to override."
            )
        return seq

    print("Running scene detection")

    scene_list = None

    untouched_scene_list = cache_file_path + ".untouched"
    if cache_path_is_valid:
        if os.path.exists(untouched_scene_list):
            print("Found untouched scene cache... loading")
            scene_list = json.load(open(untouched_scene_list))

    framerate: float = Ffmpeg.get_video_frame_rate(PathAlabama(input_file))
    width: int = Ffmpeg.get_width(PathAlabama(input_file))
    height: int = Ffmpeg.get_height(PathAlabama(input_file))

    static_length_size = int(static_length_size * framerate)

    if scene_list is None:
        if static_length:
            # create static length scenes
            total_size = Ffmpeg.get_frame_count_fast(PathAlabama(input_file))
            print(f"Using static length scenes of {static_length_size} frames")
            scene_list = [
                (i, min(i + static_length_size, total_size))
                for i in range(0, total_size, static_length_size)
            ]
        else:
            scene_list = detect(
                video_path=input_file,
                detector=AdaptiveDetector(
                    window_width=10, adaptive_threshold=2.5, min_content_val=12
                ),
                show_progress=True,
            )
            scene_list = [
                (scene[0].get_frames(), scene[1].get_frames()) for scene in scene_list
            ]

        if cache_path_is_valid:
            json.dump(scene_list, open(untouched_scene_list, "w"))

    max_length_frames = int(max_scene_length * framerate)
    if scene_merge and not static_length:
        new_scene_list = copy.deepcopy(scene_list)
        i = 1
        while i < len(new_scene_list):
            prev_start, prev_end = new_scene_list[i - 1]
            start, end = new_scene_list[i]
            if end - prev_start < 2 * max_length_frames:
                new_scene_list[i - 1] = (prev_start, end)
                print(
                    f"Merging scenes {i - 1} and {i} into {prev_start} - {end} ({end - prev_start} frames)"
                )
                del new_scene_list[i]
            else:
                i += 1

        scene_list = new_scene_list

    seq.input_file = input_file

    seq.chunks = []

    max_duration_frames = int(max_scene_length * framerate)

    # iterate through each scene detected in the video
    for scene in scene_list:
        start_frame, end_frame = scene
        duration = end_frame - start_frame

        # if the scene duration is shorter than max_scene_length, add it as a chunk to the sequence
        if duration <= max_duration_frames or static_length or scene_merge:
            seq.chunks.append(
                ChunkObject(
                    start_frame,
                    end_frame,
                    path=input_file,
                    framerate=framerate,
                    width=width,
                    height=height,
                )
            )
        else:
            # otherwise, split the scene into multiple chunks that are shorter than max_scene_length
            num_chunks = int(duration / max_duration_frames) + 1
            chunk_duration = duration / num_chunks
            for j in range(num_chunks):
                start = int(start_frame + j * chunk_duration)
                end = int(start_frame + (j + 1) * chunk_duration)
                if j == num_chunks - 1:
                    end = end_frame  # add any remaining frames to the last chunk
                seq.chunks.append(
                    ChunkObject(
                        start,
                        end,
                        path=input_file,
                        framerate=framerate,
                        width=width,
                        height=height,
                    )
                )

    if len(seq.chunks) == 0:
        print("Scene detection failed, falling back to a single chunk")
        seq.chunks.append(
            ChunkObject(
                0,
                Ffmpeg.get_frame_count(PathAlabama(input_file)),
                path=input_file,
                framerate=framerate,
                width=width,
                height=height,
            )
        )

    for i, chunk in enumerate(seq.chunks):
        chunk.chunk_index = i

    # cut any scenes that are in the offsets if a scene is at the border of the offset, cut it, so it fits
    if start_offset != -1 or end_offset != -1:
        new_chunks = []
        current_position = 0
        total_duration = Ffmpeg.get_video_length(PathAlabama(input_file))
        end_offset = total_duration - end_offset if end_offset != -1 else total_duration

        kept_chunks = []
        discarded_chunks = []

        for chunk in seq.chunks:
            # Calculate the chunk duration in seconds
            chunk_duration: float = chunk.get_lenght()

            # Calculate the start and end positions of the chunk
            chunk_start = current_position
            chunk_end = current_position + chunk_duration

            # Check if the chunk is entirely outside the bounds
            if (start_offset != -1 and chunk_end <= start_offset) or (
                end_offset != -1 and chunk_start >= end_offset
            ):
                # Chunk is entirely outside the bounds, discard it
                current_position += chunk_duration
                discarded_chunks.append(chunk.chunk_index)
                # print(f'Discarding chunk {chunk.chunk_index}')
                continue

            # Check if the chunk is entirely within the bounds
            if (start_offset == -1 or chunk_start >= start_offset) and (
                end_offset == -1 or chunk_end <= end_offset
            ):
                # Chunk is entirely within the bounds, include it in the new chunks
                kept_chunks.append(chunk.chunk_index)
                # print(f'Keeping chunk {chunk.chunk_index}')
                new_chunks.append(chunk)
            else:
                # Adjust the chunk start and end positions based on the offsets
                if start_offset != -1 and chunk_start < start_offset:
                    # Chunk starts before the start offset, adjust the start position
                    chunk_start = start_offset

                if end_offset != -1 and chunk_end > end_offset:
                    # Chunk ends after the end offset, adjust the end position
                    chunk_end = end_offset

                # Calculate the new chunk duration and frame indexes
                new_chunk_duration = chunk_end - chunk_start
                new_start_frame = int(
                    chunk.first_frame_index
                    + (chunk_start - current_position) * framerate
                )
                new_end_frame = int(new_start_frame + new_chunk_duration * framerate)

                print(
                    f"Cutting chunk {chunk.chunk_index} to {new_start_frame} - {new_end_frame}"
                )

                # Create a new chunk object with the updated values
                new_chunk = ChunkObject(
                    new_start_frame,
                    new_end_frame,
                    path=input_file,
                    framerate=framerate,
                    width=width,
                    height=height,
                )
                new_chunks.append(new_chunk)

            # Update the current position for the next chunk
            current_position = chunk_end

        if len(kept_chunks) == 0:
            raise Exception(
                "ERROR No chunks kept after cutting offsets, did you set the parameters correctly?"
            )

        print(f"keeping chunks {min(kept_chunks)}-{max(kept_chunks)}")
        print(f"discarding chunks {min(discarded_chunks)}-{max(discarded_chunks)}")

        # Replace the old list of chunks with the new one
        seq.chunks = new_chunks

    # test to see if any frames overlap
    # for i in range(len(seq.chunks) - 1):
    #     if seq.chunks[i].last_frame_index >= seq.chunks[i + 1].first_frame_index:
    #         print(
    #             f"Chunks {seq.chunks[i].chunk_index} and {seq.chunks[i + 1].chunk_index} overlap, "
    #             f"this should not happen"
    #         )
    # fix the overlap by cutting the first chunk
    # seq.chunks[i].last_frame_index = seq.chunks[i + 1].first_frame_index - 1

    # test to see if any frames are missing
    # for i in range(len(seq.chunks) - 1):
    #     if seq.chunks[i].last_frame_index + 1 != seq.chunks[i + 1].first_frame_index:
    #         print(
    #             f"Chunks {seq.chunks[i].chunk_index} and {seq.chunks[i + 1].chunk_index} are missing frames, "
    #             f"this should not happen"
    #         )
    # fix the missing frames by adding them to the first chunk
    # seq.chunks[i].last_frame_index = seq.chunks[i + 1].first_frame_index - 1

    # add chunk indexes, this has to be done after because scenes can be split, and keeping track of the index
    # would be painful
    for i, chunk in enumerate(seq.chunks):
        chunk.chunk_index = i

    # print all scenes
    # for i, chunk in enumerate(seq.chunks):
    #     print(
    #         f"Scene {i}: {chunk.first_frame_index} - {chunk.last_frame_index} ({chunk.get_lenght():.2f}s)"
    #     )

    if cache_path_is_valid:
        open(cache_file_path, "w").write(seq.dump_json())

    print(f"Detected {len(seq)} scenes")
    return seq
