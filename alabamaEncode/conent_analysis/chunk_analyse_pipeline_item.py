from abc import ABC, abstractmethod

from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.scene.chunk import ChunkObject


class ChunkAnalyzePipelineItem(ABC):
    """
    Sets up an Encoder for the final encoding, sometimes does analysis to find the parameters but doesn't have to
    """

    @abstractmethod
    def run(
        self,
        ctx,
        chunk: ChunkObject,
        enc: Encoder,
    ) -> Encoder:
        pass
