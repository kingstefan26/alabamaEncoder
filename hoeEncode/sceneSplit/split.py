import math
import os
import pickle

from scenedetect import detect, AdaptiveDetector

from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.Chunks import ChunkSequence
from hoeEncode.utils.getheight import get_height
from hoeEncode.utils.getvideoframerate import get_video_frame_rate
from hoeEncode.utils.getwidth import get_width


def get_video_scene_list_skinny(input_file: str, cache_file_path: str, max_scene_length: int) -> ChunkSequence:
    """
    :param input_file: input file
    :param cache_file_path: path that the cache will be saved to
    :param max_scene_length: max scene length in seconds,
     cut the scene in the middle recursively until max_scene_length is reached
    :return:
    """
    if os.path.exists(cache_file_path):
        print('Found scene cache... loading')
        seq: ChunkSequence = pickle.load(open(cache_file_path, 'rb'))

        # Ensure input file matches the cached sequence
        if seq.input_file != input_file:
            raise Exception(
                f'Video ({input_file}) does not match scene cache ({cache_file_path}),'
                f' please correct this (wrong temp folder?)'
            )
    else:
        print('Creating scene cache')
        scene_list = detect(video_path=input_file, detector=AdaptiveDetector(), show_progress=True)
        scene_list_frames = [[scene[0].get_frames(), scene[1].get_frames()] for scene in scene_list]

        seq = ChunkSequence([])
        seq.input_file = input_file

        framerate: float = get_video_frame_rate(input_file)
        width: int = get_width(in_path=input_file)
        height: int = get_height(in_path=input_file)

        # seq.chunks = [ChunkObject(scene[0], scene[1],
        #                           path=input_file, chunk_index=i, framerate=framerate, width=width, height=height)
        #               for i, scene in enumerate(scene_list_frames)]
        seq.chunks = []

        max_duration_frames = int(max_scene_length * framerate)

        # iterate through each scene detected in the video
        for scene in scene_list:
            start_frame = scene[0].get_frames()
            end_frame = scene[1].get_frames()
            duration = end_frame - start_frame

            # if the scene duration is shorter than max_scene_length, add it as a chunk to the sequence
            if duration <= max_duration_frames:
                seq.chunks.append(
                    ChunkObject(start_frame, end_frame, path=input_file, chunk_index=-1, framerate=framerate,
                                width=width, height=height))
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
                        ChunkObject(start, end, path=input_file, chunk_index=-1, framerate=framerate, width=width,
                                    height=height))

        # add chunk indexes, this has to be done after because we scenes can be split, and keeping track of the index
        # would be painful
        for i, chunk in enumerate(seq.chunks):
            chunk.chunk_index = i

        print(f'Saving scene cache to {cache_file_path}')
        pickle.dump(seq, open(cache_file_path, 'wb'))

    print(f'Found {len(seq)} scenes')
    return seq
