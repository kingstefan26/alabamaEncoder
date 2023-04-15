import logging
import os
from typing import List

from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.split import get_video_scene_list


def path_setup(test_env):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if not os.path.exists(test_env):
        os.mkdir(test_env)


def get_test_scenes(vid_path: str, cache_path: str = None):
    if cache_path is None:
        cache_path = './scenecache.json'
        cache_path = os.path.abspath(cache_path)
    return get_video_scene_list(vid_path, cache_path, skip_check=True)


def get_a_chunk(chunk_index: int, scene_list: List[List[float]], path):
    if len(scene_list) <= chunk_index:
        chunk_index = int(len(scene_list) / 2)
        print("Chunk index out of range, using " + str(chunk_index) + " instead")

    scene = scene_list[chunk_index]
    return ChunkObject(
        path=path,
        first_frame_index=scene[0],
        last_frame_index=scene[1]
    )
