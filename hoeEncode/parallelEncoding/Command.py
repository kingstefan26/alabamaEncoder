from abc import abstractmethod

from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob

# abstract class
class CommandObject:
    def __init__(self):
        self.config: EncoderConfigObject = None
        self.job: EncoderJob = None
        self.chunk = None

    @abstractmethod
    def run(self):
        pass

    def setup(self, job: EncoderJob, config: EncoderConfigObject):
        self.job = job
        self.chunk = job.chunk
        self.config = config

def run_command(command: CommandObject):
    command.run()