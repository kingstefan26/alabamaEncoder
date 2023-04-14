from typing import List

from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject


class ChunkSequence:
    """
    A sequence of chunks.
    """
    def __init__(self, chunks: List[ChunkObject]):
        self.chunks = chunks