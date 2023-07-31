from abc import abstractmethod
from typing import Any

from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob


class BaseCommandObject(object):
    @abstractmethod
    def run(self) -> Any:
        pass


# abstract class
class CommandObject(BaseCommandObject):
    def __init__(self):
        self.config: EncoderConfigObject = None
        self.job: EncoderJob = None
        self.chunk = None

    @abstractmethod
    def run(self) -> Any:
        pass

    def setup(self, job: EncoderJob, config: EncoderConfigObject):
        self.job = job
        self.chunk = job.chunk
        self.config = config


def run_command(command: BaseCommandObject):
    return command.run()
