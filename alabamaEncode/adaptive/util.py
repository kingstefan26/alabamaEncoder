import copy
import os
import random
from typing import List

from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


def get_probe_file_base(encoded_scene_path, temp_folder) -> str:
    """
    This filename will be used to craete grain/rate probes
    eg:
    if filename is "./test/1.ivf"
    then ill create
    "./test/1_rate_probes/probe.bitrate.speed12.grain0.ivf"
    "./test/1_rate_probes/probe.bitrate.speed12.grain1.ivf"
    "./test/1_rate_probes/probe.grain0.speed12.avif"
    etc
    """
    encoded_scene_path = copy.deepcopy(encoded_scene_path)
    path_without_file = os.path.dirname(encoded_scene_path)
    filename = os.path.basename(encoded_scene_path)
    filename_without_ext = os.path.splitext(filename)[0]
    # new folder for the rate probes
    probe_folder_path = os.path.join(
        temp_folder, path_without_file, filename_without_ext + "_rate_probes"
    )
    # make the folder
    os.makedirs(probe_folder_path, exist_ok=True)
    # new file base
    return os.path.join(probe_folder_path, filename_without_ext)


def get_test_chunks_out_of_a_sequence(
    chunk_sequence: ChunkSequence, random_pick_count: int = 7
) -> List[ChunkObject]:
    """
    Get a list of chunks from a sequence for testing, does not modify the original sequence
    :param chunk_sequence:
    :param random_pick_count: Number of random chunks to pick
    :return: List of Chunk objects
    """
    chunks_copy: List[ChunkObject] = copy.deepcopy(chunk_sequence.chunks)
    chunks_copy = chunks_copy[int(len(chunks_copy) * 0.2) : int(len(chunks_copy) * 0.8)]

    if len(chunks_copy) > 10:
        # bases on length, remove every x scene from the list so its shorter
        chunks_copy = chunks_copy[:: int(len(chunks_copy) / 10)]

    random.shuffle(chunks_copy)
    chunks = chunks_copy[:random_pick_count]

    if len(chunks) == 0:
        print("Failed to shuffle chunks for analysis, using all")
        chunks = chunk_sequence.chunks

    return copy.deepcopy(chunks)
