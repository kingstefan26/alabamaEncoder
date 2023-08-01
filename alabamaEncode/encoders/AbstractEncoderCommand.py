import os

from alabamaEncode.encoders.AbstractEncoder import AbstractEncoder
from alabamaEncode.encoders.EncoderConfig import EncoderConfigObject
from alabamaEncode.encoders.EncoderJob import EncoderJob
from alabamaEncode.parallelEncoding.Command import CommandObject


class EncoderKommand(CommandObject):
    def __init__(self, encoder_impl: AbstractEncoder):
        super().__init__()
        self.config = None
        self.job = None
        self.encoder_impl = encoder_impl

    def setup(self, job: EncoderJob, config: EncoderConfigObject):
        super().setup(job, config)
        self.encoder_impl.eat_job_config(job, config)

    def run(self):
        self.encoder_impl.run()
        if not os.path.exists(self.job.chunk.chunk_path):
            raise RuntimeError(
                "FATAL: ENCODE FAILED, PATH: " + self.job.chunk.chunk_path
            )
