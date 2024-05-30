from abc import ABC, abstractmethod

from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.scene.chunk import ChunkObject


class FinalEncodeStep(ABC):
    """
    Preforms the final (usually longer) encoding
    """

    @abstractmethod
    def run(
        self,
        enc: Encoder,
        chunk: ChunkObject,
        ctx: AlabamaContext,
        encoded_a_frame,
    ) -> EncodeStats:
        pass

    @abstractmethod
    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        pass
