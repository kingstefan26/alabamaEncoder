from abc import abstractmethod
from typing import Any

from alabamaEncode.encoders.EncoderConfig import EncoderConfigObject
from alabamaEncode.sceneSplit.ChunkOffset import ChunkObject


class BaseCommandObject(object):
    @abstractmethod
    def run(self) -> Any:
        pass


# abstract class
class CommandObject(BaseCommandObject):
    def __init__(self):
        self.config: EncoderConfigObject
        self.chunk: ChunkObject

    @abstractmethod
    def run(self) -> Any:
        pass

    def setup(self, chunk: ChunkObject, config: EncoderConfigObject):
        self.chunk = chunk
        self.config = config


def run_command(command: BaseCommandObject):
    return command.run()
