import os.path

from hoeEncode.encode.AbstractEncoder import AbstractEncoder
from hoeEncode.encode.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderJob, EncoderConfigObject
from paraliezeMeHoe.ThaVaidioEncoda import KummandObject


class EncoderKommand(KummandObject):
    def __init__(self, config: EncoderConfigObject, job: EncoderJob, encoder_impl: AbstractEncoder):
        self.config = config
        self.job = job
        self.encoder_impl = encoder_impl

    def run(self):
        self.encoder_impl.eat_job_config(self.job, self.config)
        self.encoder_impl.run()
        self.output_check(self.job.encoded_scene_path)


    def get_dry_run(self):
        enc = self.encoder_impl
        enc.eat_job_config(self.job, self.config)
        command = ''
        for k in enc.get_encode_commands():
            command += k + ' && '
        return command
