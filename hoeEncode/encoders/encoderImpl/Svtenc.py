import os.path
from typing import List

from hoeEncode.encoders.AbstractEncoder import AbstractEncoder
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.ffmpegUtil import syscmd, get_width, get_height
from hoeEncode.sceneSplit.ChunkUtil import create_chunk_ffmpeg_pipe_command_using_chunk


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
    film_grain_denoise: (0 | 1) = 1  # denoise the image when apling grain synth, turn off if you want preserve more

    # detail and use grain

    def get_encode_commands(self) -> List[str]:
        if self.chunk is None:
            raise Exception('FATAL: chunk is None')
        if self.temp_folder is None:
            raise Exception('FATAL: temp_folder is None')
        if self.current_scene_index is None:
            raise Exception('FATAL: current_scene_index is None')

        # kommand = f'ffmpeg -v error -y {self.chunk.get_ss_ffmpeg_command_pair()}
        # -c:v libsvtav1 {self.crop_string} -threads {self.threads}
        # -g 9999 -passlogfile {self.temp_folder}{self.current_scene_index}svt'
        kommand = f'{create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=self.chunk, bit_depth=10, crop_string=self.crop_string)} | ' \
                  f'SvtAv1EncApp' \
                  f' -i stdin' \
                  f' --input-depth 10' \
                  f' -w {get_width(self.chunk.path)}' \
                  f' -h {get_height(self.chunk.path)}' \
                  f' --keyint 9999'

        if self.crf is not None and self.crf > 63:
            raise Exception('FATAL: crf must be less than 63')

        match self.rate_distribution:
            case RateDistribution.CQ:
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
        kommand += ' --scd 0'  # disable scene change detection
        kommand += ' --enable-qm 1'  # enable quantization matrix
        kommand += ' --qm-min 8'  # min quantization matrix
        kommand += ' --qm-max 15'  # max quantization matrix
        kommand += ' --chroma-u-dc-qindex-offset -2'
        kommand += ' --chroma-u-ac-qindex-offset -2'
        kommand += ' --chroma-v-dc-qindex-offset -2'
        kommand += ' --chroma-v-ac-qindex-offset -2'

        if self.passes == 2:
            return [
                f'{kommand} --passes 2 --stats {self.temp_folder}{self.current_scene_index}svt.stat -b {self.output_path}'
            ]
        elif self.passes == 1:
            # enable-overlays=1 - enable additional overlay frame thing
            # irefresh-type=1 - open gop
            return [
                f'{kommand} --enable-overlays 1 --irefresh-type 1 --passes 1 -b {self.output_path}'
            ]
        elif self.passes == 3:
            return [
                f'{kommand} --passes 3 --stats {self.temp_folder}{self.current_scene_index}svt.stat -b {self.output_path}'
            ]
        else:
            raise Exception(f'FATAL: invalid passes count {self.passes}')
