import os

from tqdm import tqdm

from hoeEncode.encoders.Encoders import EncodersEnum
from hoeEncode.encoders.RateDiss import RateDistribution


class EncoderConfigObject:
    """ A class to hold the configuration for the encoder """
    crop_string = ''
    bitrate: int = 0
    temp_folder = ''
    server_ip = ''
    remote_path = ''
    convexhull = False
    vmaf: int
    ssim_db_target = 20
    grain_synth = -1
    passes = 3
    crf = -1
    speed = 4
    rate_distribution: RateDistribution
    threads: int = 1
    qm_enabled = False
    qm_min = 8
    qm_max = 15
    film_grain_denoise: (0 | 1) = 1
    crf_bitrate_mode = False
    max_bitrate = 0
    encoder: EncodersEnum = None
    content_type = 'live_action'
    bitrate_undershoot = 0.90
    bitrate_overshoot = 2
    bitrate_adjust_mode = 'chunk'
    use_celery = False
    multiprocess_workers = -1
    log_level = 0

    def log(self, msg, level=0):
        if self.log_level > 0 and level <= self.log_level:
            tqdm.write(msg)

    def __init__(self, crop_string='', bitrate=0, temp_folder='', server_ip='', remote_path='', convexhull=False,
                 vmaf=96, grain_synth=-1, passes=2, crf=-1, speed=3, rate_distribution=RateDistribution.VBR, threads=1,
                 ssim_db_target=20, qm_enabled=False, qm_min=8, qm_max=15, encoder='svt_av1',
                 content_type='live_action', log_level=0):
        self.crop_string = crop_string
        self.log_level = log_level
        self.ssim_db_target = ssim_db_target
        self.bitrate = bitrate
        self.temp_folder = temp_folder
        self.server_ip = server_ip
        self.remote_path = remote_path
        self.convexhull = convexhull
        self.vmaf = vmaf
        self.grain_synth = grain_synth
        self.passes = passes
        self.crf = crf
        self.speed = speed
        self.rate_distribution = rate_distribution
        self.threads = threads
        self.qm_enabled = qm_enabled
        self.qm_min = qm_min
        self.qm_max = qm_max
        self.encoder = EncodersEnum.from_str(encoder)
        self.content_type = content_type

    def update(self, **kwargs):
        """
        Update the config with new values, with type checking
        """
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
        if 'passes' in kwargs:
            self.passes = kwargs.get('passes')
            if not isinstance(self.passes, int):
                raise Exception('FATAL: passes must be an int')
        if 'crop_string' in kwargs:
            self.crop_string = kwargs.get('crop_string')
            if not isinstance(self.crop_string, str):
                raise Exception('FATAL: crop_string must be a str')
        if 'speed' in kwargs:
            self.speed = kwargs.get('speed')
            if not isinstance(self.speed, int):
                raise Exception('FATAL: speed must be an int')
        if 'threads' in kwargs:
            self.threads = kwargs.get('threads')
            if not isinstance(self.threads, int):
                raise Exception('FATAL: threads must be an int')
        if 'rate_distribution' in kwargs:
            self.rate_distribution = kwargs.get('rate_distribution')
            if not isinstance(self.rate_distribution, RateDistribution):
                raise Exception('FATAL: rate_distribution must be an RateDistribution')
        if 'qm_enabled' in kwargs:
            self.qm_enabled = kwargs.get('qm_enabled')
            if not isinstance(self.qm_enabled, bool):
                raise Exception('FATAL: qm_enabled must be an bool')
        if 'qm_min' in kwargs:
            self.qm_min = kwargs.get('qm_min')
            if not isinstance(self.qm_min, int):
                raise Exception('FATAL: qm_min must be an int')
        if 'qm_max' in kwargs:
            self.qm_max = kwargs.get('qm_max')
            if not isinstance(self.qm_max, int):
                raise Exception('FATAL: qm_max must be an int')
        if 'content_type' in kwargs:
            self.content_type = kwargs.get('content_type')
            if not isinstance(self.content_type, str):
                raise Exception('FATAL: content_type must be an str')
