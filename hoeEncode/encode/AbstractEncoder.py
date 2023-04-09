import os
from typing import List

from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
from hoeEncode.encode.ffmpeg.FfmpegUtil import syscmd


class AbstractEncoder:
    chunk: ChunkObject = None
    temp_folder: str
    bitrate: int = None
    crf: str = None
    current_scene_index: int
    passes: int = 2
    crop_string: str = ""
    output_path: str
    speed = 3
    first_pass_speed = 8
    svt_grain_synth = 10
    threads = 1
    tune = 0
    rate_distribution = 2  # :param mode: 0:VBR 1:CQ 2:CQ VBV 3:VBR VBV

    def update(self, **kwargs):
        if 'chunk' in kwargs:
            self.chunk = kwargs.get('chunk')
        if 'temp_folder' in kwargs:
            self.temp_folder = kwargs.get('temp_folder')
        if 'bitrate' in kwargs:
            self.bitrate = kwargs.get('bitrate')
        if 'crf' in kwargs:
            self.crf = kwargs.get('crf')
        if 'current_scene_index' in kwargs:
            self.current_scene_index = kwargs.get('current_scene_index')
        if 'passes' in kwargs:
            self.passes = kwargs.get('passes')
        if 'crop_string' in kwargs:
            self.crop_string = kwargs.get('crop_string')
        if 'output_path' in kwargs:
            self.output_path = kwargs.get('output_path')
        if 'speed' in kwargs:
            self.speed = kwargs.get('speed')
        if 'first_pass_speed' in kwargs:
            self.first_pass_speed = kwargs.get('first_pass_speed')
        if 'svt_grain_synth' in kwargs:
            self.svt_grain_synth = kwargs.get('svt_grain_synth')
        if 'threads' in kwargs:
            self.threads = kwargs.get('threads')
        if 'tune' in kwargs:
            self.tune = kwargs.get('tune')
        if 'rate_distribution' in kwargs:
            self.rate_distribution = kwargs.get('rate_distribution')

    def run(self, override_if_exists=True):
        if os.path.exists(self.output_path) and not override_if_exists:
            return

        out = []
        for command in self.get_encode_commands():
            out.append(syscmd(command))

        if not os.path.exists(self.output_path):
            raise Exception('FATAL: ENCODE FAILED ' + str(out))

    def get_encode_commands(self) -> List[str]:
        pass
