from hoeEncode.encoders.RateDiss import RateDistribution


class EncoderConfigObject:
    """ A class to hold the configuration for the encoder """
    two_pass = True
    crop_string = ''
    bitrate: int = 0
    temp_folder = ''
    server_ip = ''
    remote_path = ''
    dry_run = False
    convexhull = False
    vmaf = 94
    grain_synth = -1
    passes = 2
    crf = -1
    speed = 3
    rate_distribution: RateDistribution
    threads: int = 1

    def __init__(self, two_pass=True, crop_string='', bitrate=0, temp_folder='', server_ip='', remote_path='',
                 dry_run=False, convexhull=False, vmaf=94, grain_synth=-1, passes=2, crf=-1, speed=3,
                 rate_distribution=RateDistribution.VBR, threads=1):
        self.two_pass = two_pass
        self.crop_string = crop_string
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
