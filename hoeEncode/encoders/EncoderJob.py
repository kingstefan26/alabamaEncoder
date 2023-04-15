from hoeEncode.sceneSplit.ChunkOffset import ChunkObject


class EncoderJob:
    """ A class to hold the configuration for the encoder """

    def __init__(self, chunk: ChunkObject, current_scene_index: int, encoded_scene_path: str):
        self.chunk = chunk
        self.current_scene_index = current_scene_index
        self.encoded_scene_path = encoded_scene_path

    chunk: ChunkObject
    current_scene_index: int
    encoded_scene_path: str
