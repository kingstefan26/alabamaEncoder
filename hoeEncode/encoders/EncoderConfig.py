from hoeEncode.encoders.RateDiss import RateDistribution


class EncoderConfigObject:
    """ A class to hold the configuration for the encoder """
    crop_string = ''
    bitrate: int = 0
    temp_folder = ''
    server_ip = ''
    remote_path = ''
    dry_run = False
    convexhull = False
    vmaf = 96
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

    def __init__(self, crop_string='', bitrate=0, temp_folder='', server_ip='', remote_path='',
                 dry_run=False, convexhull=False, vmaf=94, grain_synth=-1, passes=2, crf=-1, speed=3,
                 rate_distribution=RateDistribution.VBR, threads=1, ssim_db_target=20, qm_enabled=False, qm_min=8,
                 qm_max=15):
        self.crop_string = crop_string
        self.ssim_db_target = ssim_db_target
        self.bitrate = bitrate
        self.temp_folder = temp_folder
        self.server_ip = server_ip
        self.remote_path = remote_path
        self.dry_run = dry_run
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
