import copy
import os
import random
from typing import List

from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


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
    chunks_copy = chunks_copy[int(len(chunks_copy) * 0.2): int(len(chunks_copy) * 0.8)]

    if len(chunks_copy) > 10:
        # bases on length, remove every x scene from the list so its shorter
        chunks_copy = chunks_copy[:: int(len(chunks_copy) / 10)]

    random.shuffle(chunks_copy)
    chunks = chunks_copy[:random_pick_count]

    if len(chunks) == 0:
        print("Failed to shuffle chunks for analysis, using all")
        chunks = chunk_sequence.chunks

    return copy.deepcopy(chunks)


def get_probe_file_base(encoded_scene_path) -> str:
    """
    :argument encoded_scene_path: /home/test/out/temp/1.ivf
    return /home/test/out/temp/1_rate_probes

    another:
    /home/test/out/temp/42.ivf -> /home/test/out/temp/42_rate_probes/
    """
    # get base file name without an extension
    file_without_extension = os.path.splitext(os.path.basename(encoded_scene_path))[0]

    # temp folder
    path_without_file = os.path.dirname(encoded_scene_path)

    # join
    probe_folder_path = os.path.join(
        path_without_file, (file_without_extension + "_rate_probes")
    )

    # add trailing slash
    probe_folder_path += os.path.sep

    os.makedirs(probe_folder_path, exist_ok=True)
    # new file base
    return probe_folder_path
