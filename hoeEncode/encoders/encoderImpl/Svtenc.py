import os.path
from typing import List

from hoeEncode.encoders.AbstractEncoder import AbstractEncoder
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.sceneSplit.ChunkUtil import create_chunk_ffmpeg_pipe_command_using_chunk
from hoeEncode.utils.execute import syscmd
from hoeEncode.utils.getheight import get_height
from hoeEncode.utils.getwidth import get_width


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

    def get_encode_commands(self) -> str:
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

        return f'ffmpeg -y -i {self.in_path} -c:v libsvtav1 {ratebit} -svtav1-params tune=0:lp={self.threads}:film-grain={self.grain_synth} -preset {self.speed} -pix_fmt {pix_fmt} {self.output_path}'

    def run(self):
        out = syscmd(self.get_encode_commands())
        if not os.path.exists(self.output_path):
            raise Exception('FATAL: SVTENC FAILED with ' + out)


class AbstractEncoderSvtenc(AbstractEncoder):
    bias_pct = 50
    open_gop = True

    keyint: int = 9999
    sdc: int = 0
    chroma_thing = -2

    def get_encode_commands(self) -> List[str]:
        if self.chunk is None:
            raise Exception('FATAL: chunk is None')
        # if self.temp_folder is None:
        #     raise Exception('FATAL: temp_folder is None')
        if self.current_scene_index is None:
            raise Exception('FATAL: current_scene_index is None')

        if (self.keyint == -1 or self.keyint == -2) and self.rate_distribution == RateDistribution.VBR:
            print('WARNING: keyint must be set for VBR, setting to 240')
            self.keyint = 240

        # kommand = f'ffmpeg -v error -y {self.chunk.get_ss_ffmpeg_command_pair()}
        # -c:v libsvtav1 {self.crop_string} -threads {self.threads}
        # -g 9999 -passlogfile {self.temp_folder}{self.current_scene_index}svt'
        kommand = f'{create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=self.chunk, bit_depth=10, crop_string=self.crop_string)} | ' \
                  f'SvtAv1EncApp' \
                  f' -i stdin' \
                  f' --input-depth 10' \
                  f' -w {get_width(self.chunk.path)}' \
                  f' -h {get_height(self.chunk.path)}' \
                  f' --keyint {self.keyint}'

        if self.crf is not None and self.crf > 63:
            raise Exception('FATAL: crf must be less than 63')

        match self.rate_distribution:
            case RateDistribution.CQ:
                if self.passes != 1:
                    print('WARNING: passes must be 1 for CQ, setting to 1')
                    self.passes = 1
                if self.crf is None or self.crf == -1:
                    raise Exception('FATAL: crf must be set for CQ')
                kommand += f' --crf {self.crf}'
            case RateDistribution.VBR:
                if self.bitrate is None or self.bitrate == -1:
                    raise Exception('FATAL: bitrate must be set for VBR')
                kommand += f' --rc 1 --tbr {self.bitrate}'
            case RateDistribution.CQ_VBV:
                if self.crf is None or self.crf == -1:
                    raise Exception('FATAL: crf must be set for CQ_VBV')
                if self.bitrate is None or self.bitrate == -1:
                    raise Exception('FATAL: bitrate must be set for CQ_VBV')
                kommand += f' --crf {self.crf} --tbr {self.bitrate}'
            case RateDistribution.VBR_VBV:
                if self.bitrate is None or self.bitrate == -1:
                    raise Exception('FATAL: bitrate must be set for VBR_VBV')
                kommand += f' --tbr {self.bitrate} --mbr {self.bitrate * 1.5}'

        kommand += f' --tune 0'  # tune for PsychoVisual Optimization
        kommand += f' --bias-pct {self.bias_pct}'  # 100 vbr like, 0 cbr like
        kommand += f' --lp {self.threads}'  # threads

        if 0 <= self.svt_grain_synth <= 50:
            kommand += f' --film-grain {self.svt_grain_synth}'  # grain synth

        kommand += f' --preset {self.speed}'  # speed
        kommand += f' --film-grain-denoise {self.film_grain_denoise}'
        if self.qm_enabled:
            kommand += f' --qm-min {self.qm_min}'  # min quantization matrix
            kommand += f' --qm-min {self.qm_min}'  # min quantization matrix
            kommand += f' --qm-max {self.qm_max}'  # max quantization matrix
            kommand += ' --enable-qm 1'
        else:
            kommand += ' --enable-qm 0'

        kommand += f' --scd {self.sdc}'  # scene detection

        if self.chroma_thing != 0:
            kommand += f' --chroma-u-dc-qindex-offset {self.chroma_thing}'
            kommand += f' --chroma-u-ac-qindex-offset {self.chroma_thing}'
            kommand += f' --chroma-v-dc-qindex-offset {self.chroma_thing}'
            kommand += f' --chroma-v-ac-qindex-offset {self.chroma_thing}'

        stats_bit = ''

        if self.passes > 1:
            stats_bit = f'--stats {self.output_path}.stat'

        if self.open_gop and self.passes == 1:
            kommand += ' --irefresh-type 1'

        if self.passes == 2:
            return [
                f'{kommand} --pass 1 {stats_bit}',
                f'{kommand} --pass 2 {stats_bit} -b {self.output_path}'
            ]
        elif self.passes == 1:
            # enable-overlays=1 - enable additional overlay frame thing
            return [
                f'{kommand} --enable-overlays 1 --passes 1 -b {self.output_path}'
            ]
        elif self.passes == 3:
            return [
                f'{kommand} --pass 1 {stats_bit}',
                f'{kommand} --pass 2 {stats_bit}',
                f'{kommand} --pass 3 {stats_bit} -b {self.output_path}'
            ]
        else:
            raise Exception(f'FATAL: invalid passes count {self.passes}')
