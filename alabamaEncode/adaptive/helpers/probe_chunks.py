import copy
import random
from typing import List

from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


def get_test_chunks_out_of_a_sequence(
    chunk_sequence: ChunkSequence, random_pick_count: int = 7
) -> List[ChunkObject]:
    """
    Get a equally distributed list of chunks from a sequence for testing, does not modify the original sequence
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
