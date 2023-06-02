import os.path
from typing import List

from hoeEncode.encoders.AbstractEncoder import AbstractEncoder
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.utils.execute import syscmd


class AvifEncoderSvtenc:
    """
    This will encode the first frame of the chunk to a PNG, then encode the PNG to AVIF.
    """

    def __init__(self, **kwargs):
        self.vf = kwargs.get('vf', ' ')
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
        if 'vf' in kwargs:
            self.vf = kwargs.get('vf')

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

        if self.bitrate is not None and self.bitrate != -1:
            ratebit = f'-b:v {self.bitrate}k'
        else:
            ratebit = f'-crf {self.crf}'

        return f'ffmpeg -hide_banner -y -i {self.in_path} {self.vf} -c:v libsvtav1 {ratebit} ' \
               f'-svtav1-params tune=0:lp={self.threads}:film-grain={self.grain_synth}' \
               f' -preset {self.speed} -pix_fmt {pix_fmt} {self.output_path}'

    def run(self):
        out = syscmd(self.get_encode_commands())
        if not os.path.exists(self.output_path) or os.path.getsize(self.output_path) < 1:
            print(self.get_encode_commands())
            raise Exception(f'FATAL: SVTENC ({self.get_encode_commands()}) FAILED with ' + out)


class AbstractEncoderSvtenc(AbstractEncoder):

    def get_encode_commands(self) -> List[str]:
        if (self.keyint == -1 or self.keyint == -2) and self.rate_distribution == RateDistribution.VBR:
            print('WARNING: keyint must be set for VBR, setting to 240')
            self.keyint = 240

        kommand = f'{self.get_ffmpeg_pipe_command()} | ' \
                  f'{self.svt_cli_path}' \
                  f' -i stdin' \
                  f' --input-depth {self.bit_override}' \
                  f' --keyint {self.keyint}'

        def crf_check():
            """
            validate crf fields
            """
            if self.crf is None or self.crf == -1:
                raise Exception('FATAL: crf is not set')
            if self.crf > 63:
                raise Exception('FATAL: crf must be less than 63')

        def bitrate_check():
            """
            validate bitrate fields
            """
            if self.bitrate is None or self.bitrate == -1:
                raise Exception('FATAL: bitrate is not set')

        match self.rate_distribution:
            case RateDistribution.CQ:
                if self.passes != 1:
                    print('WARNING: passes must be 1 for CQ, setting to 1')
                    self.passes = 1
                crf_check()
                kommand += f' --crf {self.crf}'
            case RateDistribution.VBR:
                bitrate_check()
                kommand += f' --rc 1 --tbr {self.bitrate} --undershoot-pct 95 --overshoot-pct 10 '
            case RateDistribution.CQ_VBV:
                bitrate_check()
                crf_check()
                kommand += f' --crf {self.crf} --mbr {self.max_bitrate}'
            case RateDistribution.VBR_VBV:
                bitrate_check()
                kommand += f' --tbr {self.bitrate} --mbr {self.bitrate * 1.5}'

        kommand += f' --tune {self.svt_tune}'
        kommand += f' --bias-pct {self.svt_bias_pct}'
        kommand += f' --lp {self.threads}'

        if self.svt_supperres_mode != 0:
            kommand += f' --superres-mode {self.svt_supperres_mode}'  # superres mode
            kommand += f' --superres-denom {self.svt_superres_denom}'  # superres denom
            kommand += f' --superres-kf-denom {self.svt_superres_kf_denom}'  # superres kf denom
            kommand += f' --superres-qthres {self.svt_superres_qthresh}'  # superres qthresh
            kommand += f' --superres-kf-qthres {self.svt_superres_kf_qthresh}'  # superres kf qthresh

        if self.svt_sframe_interval > 0:
            kommand += f' --sframe-dist {self.svt_sframe_interval}'
            kommand += f' --sframe-mode {self.svt_sframe_mode}'

        if 0 <= self.svt_grain_synth <= 50:
            kommand += f' --film-grain {self.svt_grain_synth}'  # grain synth

        kommand += f' --preset {self.speed}'  # speed
        # kommand += f' --film-grain-denoise {self.film_grain_denoise}'
        kommand += f' --film-grain-denoise 0'
        if self.qm_enabled:
            kommand += f' --qm-min {self.qm_min}'  # min quantization matrix
            kommand += f' --qm-max {self.qm_max}'  # max quantization matrix
            kommand += ' --enable-qm 1'
        else:
            kommand += ' --enable-qm 0'

        if self.svt_sdc != 0:
            kommand += f' --scd {self.svt_sdc}'  # scene detection

        stats_bit = ''

        if self.passes > 1:
            stats_bit = f'--stats {self.output_path}.stat'

        if self.svt_open_gop and self.passes == 1:
            kommand += ' --irefresh-type 1'

        if self.passes == 1:
            kommand += ' --enable-overlays 1'

        match self.passes:
            case 2:
                commands = [
                    f'{kommand} --pass 1 {stats_bit}',
                    f'{kommand} --pass 2 {stats_bit} -b {self.output_path}'
                ]
            case 1:
                commands = [
                    f'{kommand} -b "{self.output_path}"'
                ]
            case 3:
                commands = [
                    f'{kommand} --pass 1 {stats_bit}',
                    f'{kommand} --pass 2 {stats_bit}',
                    f'{kommand} --pass 3 {stats_bit} -b {self.output_path}'
                ]
            case _:
                raise Exception(f'FATAL: invalid passes count {self.passes}')

        return commands

    def get_chunk_file_extension(self) -> str:
        return '.ivf'

    def get_needed_path(self) -> List[str]:
        """

        :return:
        """
        return ['ffmpeg', 'SvtAv1EncApp', 'ffprobe']
