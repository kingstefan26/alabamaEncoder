import os
from typing import List

from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.ffmpegUtil import syscmd
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject


class AbstractEncoder:
    chunk: ChunkObject = None
    temp_folder: str
    bitrate: int = None
    crf: int = None
    current_scene_index: int
    passes: int = 2
    crop_string: str = ""
    output_path: str
    speed = 3
    first_pass_speed = 8
    svt_grain_synth = 10
    threads = 1
    tune = 0
    rate_distribution: RateDistribution = RateDistribution.CQ  # :param mode: 0:VBR 1:CQ 2:CQ VBV 3:VBR VBV

    def eat_job_config(self, job: EncoderJob, config: EncoderConfigObject):
        self.update(
            chunk=job.chunk,
            temp_folder=config.temp_folder,
            bitrate=config.bitrate,
            crf=config.crf,
            current_scene_index=job.current_scene_index,
            passes=config.passes,
            crop_string=config.crop_string,
            output_path=job.encoded_scene_path,
            speed=config.speed,
            svt_grain_synth=config.grain_synth,
            rate_distribution=config.rate_distribution,
        )

    def update(self, **kwargs):
        """
        Update the encoder with new values, with type checking
        """
        if 'chunk' in kwargs:
            self.chunk = kwargs.get('chunk')
            if not isinstance(self.chunk, ChunkObject):
                raise Exception('FATAL: chunk must be a ChunkObject')
        if 'temp_folder' in kwargs:
            self.temp_folder = kwargs.get('temp_folder')
            if not os.path.isdir(self.temp_folder):
                raise Exception('FATAL: temp_folder must be a valid directory')
        if 'bitrate' in kwargs:
            self.bitrate = kwargs.get('bitrate')
            if not isinstance(self.bitrate, int):
                raise Exception('FATAL: bitrate must be an int')
        if 'crf' in kwargs:
            self.crf = kwargs.get('crf')
            if not isinstance(self.crf, int):
                raise Exception('FATAL: crf must be an int')
        if 'current_scene_index' in kwargs:
            self.current_scene_index = kwargs.get('current_scene_index')
            if not isinstance(self.current_scene_index, int):
                raise Exception('FATAL: current_scene_index must be an int')
        if 'passes' in kwargs:
            self.passes = kwargs.get('passes')
            if not isinstance(self.passes, int):
                raise Exception('FATAL: passes must be an int')
        if 'crop_string' in kwargs:
            self.crop_string = kwargs.get('crop_string')
            if not isinstance(self.crop_string, str):
                raise Exception('FATAL: crop_string must be a str')
        if 'output_path' in kwargs:
            self.output_path = kwargs.get('output_path')
            if not isinstance(self.output_path, str):
                raise Exception('FATAL: output_path must be a str')
        if 'speed' in kwargs:
            self.speed = kwargs.get('speed')
            if not isinstance(self.speed, int):
                raise Exception('FATAL: speed must be an int')
        if 'first_pass_speed' in kwargs:
            self.first_pass_speed = kwargs.get('first_pass_speed')
            if not isinstance(self.first_pass_speed, int):
                raise Exception('FATAL: first_pass_speed must be an int')
        if 'svt_grain_synth' in kwargs:
            self.svt_grain_synth = kwargs.get('svt_grain_synth')
            if not isinstance(self.svt_grain_synth, int):
                raise Exception('FATAL: svt_grain_synth must be an int')
        if 'threads' in kwargs:
            self.threads = kwargs.get('threads')
            if not isinstance(self.threads, int):
                raise Exception('FATAL: threads must be an int')
        if 'tune' in kwargs:
            self.tune = kwargs.get('tune')
            if not isinstance(self.tune, int):
                raise Exception('FATAL: tune must be an int')
        if 'rate_distribution' in kwargs:
            self.rate_distribution = kwargs.get('rate_distribution')
            if not isinstance(self.rate_distribution, RateDistribution):
                raise Exception('FATAL: rate_distribution must be an RateDistribution')

    def run(self, override_if_exists=True, timeout_value=-1):
        if os.path.exists(self.output_path) and not override_if_exists:
            return

        out = []
        for command in self.get_encode_commands():
            out.append(syscmd(command, timeout_value=timeout_value))

        out_size = os.path.getsize(self.output_path)
        if not os.path.exists(self.output_path) or out_size == 0:
            raise Exception('FATAL: ENCODE FAILED ' + str(out))

    def get_encode_commands(self) -> List[str]:
        pass
