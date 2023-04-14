import os.path
from typing import List

from hoeEncode.encode.AbstractEncoder import AbstractEncoder, RateDistribution
from hoeEncode.encode.ffmpeg.FfmpegUtil import syscmd


class AvifEncoderSvtenc:
    """
    This will encode the first frame of the chunk to a PNG, then encode the PNG to AVIF.
    """

    def __init__(self, **kwargs):
        self.in_path = kwargs.get('in_path')
        self.grain_synth = kwargs.get('grain_synth', 0)
        self.output_path = kwargs.get('output_path')
        self.speed = kwargs.get('speed', 3)
        self.bitrate = kwargs.get('bitrate', None)
        self.bit_depth = kwargs.get('bit_depth', 8)
        self.crf = kwargs.get('crf', 13)
        self.passes = kwargs.get('passes', 1)
        self.threads = kwargs.get('threads', 1)

    def update(self, **kwargs):
        if 'in_path' in kwargs:
            self.in_path = kwargs.get('in_path')
        if 'grain_synth' in kwargs:
            self.grain_synth = kwargs.get('grain_synth')
        if 'output_path' in kwargs:
            self.output_path = kwargs.get('output_path')
        if 'speed' in kwargs:
            self.speed = kwargs.get('speed')
        if 'bitrate' in kwargs:
            self.bitrate = kwargs.get('bitrate')
        if 'bit_depth' in kwargs:
            self.bit_depth = kwargs.get('bit_depth')
        if 'crf' in kwargs:
            self.crf = kwargs.get('crf')
        if 'passes' in kwargs:
            self.passes = kwargs.get('passes')
        if 'threads' in kwargs:
            self.threads = kwargs.get('threads')

    in_path: str
    grain_synth: int
    output_path: str
    speed: int
    bitrate: str
    bit_depth: int
    crf: int
    passes: int
    threads: int

    def get_encode_commands(self) -> List[str]:
        if not self.output_path.endswith('.avif'):
            raise Exception('FATAL: output_path must end with .avif')

        if self.bit_depth != 8 and self.bit_depth != 10:
            raise Exception('FATAL: bit must be 8 or 10')

        if self.bit_depth == 8:
            pix_fmt = 'yuv420p'
        elif self.bit_depth == 10:
            pix_fmt = 'yuv420p10le'
        else:
            raise Exception('FATAL: bit must be 8 or 10')

        if self.bitrate is not None:
            ratebit = f'-b:v {self.bitrate}'
        else:
            ratebit = f'-crf {self.crf}'

        if self.passes == 1:
            return [
                f'ffmpeg -y -i {self.in_path} -c:v libsvtav1 {ratebit} -svtav1-params tune=0:lp={self.threads}:film-grain={self.grain_synth} -preset {self.speed} -pix_fmt {pix_fmt} {self.output_path}']
        else:
            return [
                f'ffmpeg -y -i {self.in_path} -c:v libsvtav1 {ratebit} -svtav1-params tune=0:lp={self.threads}:film-grain={self.grain_synth} -preset {self.speed} -pix_fmt {pix_fmt} -passlogfile {self.output_path} -pass 1 -f null /dev/null',
                f'ffmpeg -y -i {self.in_path} -c:v libsvtav1 {ratebit} -svtav1-params tune=0:lp={self.threads}:film-grain={self.grain_synth} -preset {self.speed} -pix_fmt {pix_fmt} -passlogfile {self.output_path} -pass 2 {self.output_path}']

    def run(self):
        for command in self.get_encode_commands():
            syscmd(command)
        if not os.path.exists(self.output_path):
            raise Exception('FATAL: SVTENC FAILED')


class AbstractEncoderSvtenc(AbstractEncoder):
    bias_pct = 50

    def get_encode_commands(self) -> List[str]:
        if self.chunk is None:
            raise Exception('FATAL: chunk is None')
        if self.temp_folder is None:
            raise Exception('FATAL: temp_folder is None')
        if self.current_scene_index is None:
            raise Exception('FATAL: current_scene_index is None')
        kommand = f'ffmpeg -v error -y {self.chunk.get_ss_ffmpeg_command_pair()} -c:v libsvtav1 {self.crop_string} -threads {self.threads} -g 9999 -passlogfile {self.temp_folder}{self.current_scene_index}svt'

        if self.crf is not None and self.crf > 63:
            raise Exception('FATAL: crf must be less than 63')

        match self.rate_distribution:
            case RateDistribution.CQ:
                if self.crf is None or self.crf == -1:
                    raise Exception('FATAL: crf must be set for CQ')
                kommand += f' -crf {self.crf}'
            case RateDistribution.VBR:
                if self.bitrate is None or self.bitrate == -1:
                    raise Exception('FATAL: bitrate must be set for VBR')
                kommand += f' -b:v {self.bitrate}k'
            case RateDistribution.CQ_VBV:
                if self.crf is None or self.crf == -1:
                    raise Exception('FATAL: crf must be set for CQ_VBV')
                if self.bitrate is None or self.bitrate == -1:
                    raise Exception('FATAL: bitrate must be set for CQ_VBV')
                kommand += f' -crf {self.crf} -maxrate {self.bitrate}k'
            case RateDistribution.VBR_VBV:
                if self.bitrate is None or self.bitrate == -1:
                    raise Exception('FATAL: bitrate must be set for VBR_VBV')
                kommand += f' -b:v {self.bitrate}k -maxrate {self.bitrate}k -bufsize -maxrate {int(self.bitrate * 2)}k'

        # Explainer
        # tune=0 - tune for PsychoVisual Optimization
        # scd=0 - disable scene change detection
        # enable-overlays=1 - enable additional overlay frame thing
        # irefresh-type=1 - open gop
        # lp=1 - threads to use
        svt_common_params = f'tune={self.tune}:scd=0:enable-overlays=1:irefresh-type=1:' \
                            f'chroma-u-dc-qindex-offset=-2:chroma-u-ac-qindex-offset=-2:chroma-v-dc-qindex-offset=-2:' \
                            f'chroma-v-ac-qindex-offset=-2:lp={self.threads}:enable-qm=1:qm-min=8:qm-max=15' \
                            f':bias-pct={self.bias_pct}'

        # NOTE:
        # I use this svt_common_params thing cuz we don't need grain synth for the first pass + its faster

        if self.passes == 2:
            return [
                f'{kommand} -svtav1-params {svt_common_params} -preset {self.first_pass_speed} -pass 1 -pix_fmt yuv420p10le -an -f null /dev/null',
                f'{kommand} -svtav1-params {svt_common_params}:film-grain={self.svt_grain_synth} -preset {self.speed} -pass 2 -pix_fmt yuv420p10le -an {self.output_path}'
            ]
        elif self.passes == 1:
            return [
                f'{kommand} -svtav1-params {svt_common_params}:film-grain={self.svt_grain_synth} -preset {self.speed} -pix_fmt yuv420p10le -an {self.output_path}'
            ]
        elif self.passes == 3:
            return [
                f'{kommand} -svtav1-params {svt_common_params} -preset {self.first_pass_speed} -pass 1 -pix_fmt yuv420p10le -an -f null /dev/null',
                f'{kommand} -svtav1-params {svt_common_params}:film-grain={self.svt_grain_synth} -preset {self.speed} -pass 2 -pix_fmt yuv420p10le -an {self.output_path}',
                f'{kommand} -svtav1-params {svt_common_params}:film-grain={self.svt_grain_synth} -preset {self.speed} -pass 3 -pix_fmt yuv420p10le -an {self.output_path}'
            ]
        else:
            raise Exception(f'FATAL: invalid passes count {self.passes}')
