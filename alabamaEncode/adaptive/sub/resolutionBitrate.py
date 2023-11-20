from alabamaEncode.adaptive.util import get_test_chunks_out_of_a_sequence
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.scene.sequence import ChunkSequence


def get_resolution_for_bitrate(
    bitrate: int, chunk_sequence: ChunkSequence, config: AlabamaContext
) -> str:
    """
    What resolution should we use for a given bitrate?
    :param bitrate: bitrate in kbps
    :param chunk_sequence: chunk sequence
    :param config: encoder config
    :return: ffmpeg crop filter scale, eg scale=1920:-2:flags=lanczos
    """
    test_chunks = get_test_chunks_out_of_a_sequence(chunk_sequence)

    pass


# prob not implementing this since its not going to be useful
def get_bitrate_for_resolution(
    resolution: str, chunk_sequence: ChunkSequence, config: AlabamaContext
) -> int:
    """
    What bitrate should we use for a given resolution?
    :param resolution: ffmpeg crop filter scale, eg scale=1920:-2:flags=lanczos
    :param chunk_sequence: chunk sequence
    :param config: encoder config
    :return: bitrate in kbps
    """
    pass
