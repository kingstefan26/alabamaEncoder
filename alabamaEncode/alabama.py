import os

from tqdm import tqdm

from alabamaEncode.encoders.encoder.encoder import AbstractEncoder
from alabamaEncode.encoders.encoderMisc import EncodersEnum, EncoderRateDistribution


class AlabamaContext:
    """A class to hold the configuration for the encoder"""

    video_filters: str = ""
    bitrate: int = 0
    temp_folder: str = ""
    vbr_perchunk_optimisation: bool = False
    vmaf: int
    ssim_db_target: float = 20
    grain_synth: int = -1
    passes: (1 or 2 or 3) = 3
    crf: float = -1
    speed: int = 4
    rate_distribution: EncoderRateDistribution
    threads: int = 1
    qm_enabled: bool = False
    qm_min: int = 8
    qm_max: int = 15
    film_grain_denoise: (0 | 1) = 1
    crf_bitrate_mode: bool = False
    max_bitrate: int = 0
    encoder: EncodersEnum = None
    bitrate_undershoot: float = 0.90
    bitrate_overshoot: float = 2
    bitrate_adjust_mode: str = "chunk"
    use_celery: bool = False
    multiprocess_workers: int = -1
    log_level: int = 0
    dry_run: bool = False
    flag1: bool = False
    flag2: bool = False
    flag3: bool = False
    cutoff_bitrate: int = -1
    override_flags: str = ""
    color_primaries: str = "bt709"
    transfer_characteristics: str = "bt709"
    matrix_coefficients: str = "bt709"
    maximum_content_light_level: str = ""
    maximum_frame_average_light_level: str = ""

    def log(self, msg, level=0):
        if self.log_level > 0 and level <= self.log_level:
            tqdm.write(msg)

    def get_encoder(self) -> AbstractEncoder:
        return self.encoder.get_encoder()

    def __init__(
        self,
        video_filters="",
        bitrate=0,
        temp_folder="",
        vbr_perchunk_optimisation=False,
        vmaf=96,
        grain_synth=-1,
        passes=2,
        crf=-1,
        speed=3,
        rate_distribution=EncoderRateDistribution.VBR,
        threads=1,
        ssim_db_target=20,
        qm_enabled=False,
        qm_min=8,
        qm_max=15,
        log_level=0,
        dry_run=False,
    ):
        self.video_filters = video_filters
        self.log_level = log_level
        self.ssim_db_target = ssim_db_target
        self.bitrate = bitrate
        self.temp_folder = temp_folder
        self.vbr_perchunk_optimisation = vbr_perchunk_optimisation
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
        self.dry_run = dry_run

    def update(self, **kwargs):
        """
        Update the config with new values, with type checking
        """
        if "temp_folder" in kwargs:
            self.temp_folder = kwargs.get("temp_folder")
            if not os.path.isdir(self.temp_folder):
                raise Exception("FATAL: temp_folder must be a valid directory")
        if "bitrate" in kwargs:
            self.bitrate = kwargs.get("bitrate")
            if not isinstance(self.bitrate, int):
                raise Exception("FATAL: bitrate must be an int")
        if "crf" in kwargs:
            self.crf = kwargs.get("crf")
            if not isinstance(self.crf, int):
                raise Exception("FATAL: crf must be an int")
        if "passes" in kwargs:
            self.passes = kwargs.get("passes")
            if not isinstance(self.passes, int):
                raise Exception("FATAL: passes must be an int")
        if "video_filters" in kwargs:
            self.video_filters = kwargs.get("video_filters")
            if not isinstance(self.video_filters, str):
                raise Exception("FATAL: video_filters must be a str")
        if "speed" in kwargs:
            self.speed = kwargs.get("speed")
            if not isinstance(self.speed, int):
                raise Exception("FATAL: speed must be an int")
        if "threads" in kwargs:
            self.threads = kwargs.get("threads")
            if not isinstance(self.threads, int):
                raise Exception("FATAL: threads must be an int")
        if "rate_distribution" in kwargs:
            self.rate_distribution = kwargs.get("rate_distribution")
            if not isinstance(self.rate_distribution, EncoderRateDistribution):
                raise Exception("FATAL: rate_distribution must be an RateDistribution")
        if "qm_enabled" in kwargs:
            self.qm_enabled = kwargs.get("qm_enabled")
            if not isinstance(self.qm_enabled, bool):
                raise Exception("FATAL: qm_enabled must be an bool")
        if "qm_min" in kwargs:
            self.qm_min = kwargs.get("qm_min")
            if not isinstance(self.qm_min, int):
                raise Exception("FATAL: qm_min must be an int")
        if "qm_max" in kwargs:
            self.qm_max = kwargs.get("qm_max")
            if not isinstance(self.qm_max, int):
                raise Exception("FATAL: qm_max must be an int")
