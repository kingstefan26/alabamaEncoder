"""
Stats class for encoders
"""
import json
from enum import Enum


class EncodeStatus(Enum):
    FAILED = 0
    DONE = 1
    UNKNOWN = 2


class EncodeStats:
    """
    Stats class for encoders
    """

    def __init__(
        self,
        time_encoding: int = -1,
        bitrate: int = -1,
        vmaf: float = -1,
        ssim: float = -1,
        status: EncodeStatus = EncodeStatus.UNKNOWN,
        size: int = -1,
        total_fps: int = -1,
        target_miss_proc: int = -1,
        rate_search_time: int = -1,
        chunk_index: int = -1,
        vmaf_percentile_1: float = -1,
        vmaf_percentile_5: float = -1,
        vmaf_percentile_10: float = -1,
        vmaf_percentile_25: float = -1,
        vmaf_percentile_50: float = -1,
        vmaf_avg: float = -1,
        basename: str = "",  # used for testing
        version: str = "",  # used for testing
        psnr_hvs: float = -1,
        psnr: float = -1,
    ):
        self.time_encoding = time_encoding
        self.bitrate = bitrate
        self.vmaf = vmaf
        self.ssim = ssim
        self.status = status
        self.size = size
        self.total_fps = total_fps
        self.target_miss_proc = target_miss_proc
        self.rate_search_time = rate_search_time
        self.chunk_index = chunk_index
        self.vmaf_percentile_1 = vmaf_percentile_1
        self.vmaf_percentile_5 = vmaf_percentile_5
        self.vmaf_percentile_10 = vmaf_percentile_10
        self.vmaf_percentile_25 = vmaf_percentile_25
        self.vmaf_percentile_50 = vmaf_percentile_50
        self.vmaf_avg = vmaf_avg
        self.basename = basename
        self.version = version

    def get_dict(self):
        stats = {
            "time_encoding": self.time_encoding,
            "bitrate": self.bitrate,
            "vmaf": self.vmaf,
            "ssim": self.ssim,
            "status": self.status.name,
            "size": self.size,
            "total_fps": self.total_fps,
            "target_miss_proc": self.target_miss_proc,
            "rate_search_time": self.rate_search_time,
            "chunk_index": self.chunk_index,
            "vmaf_percentile_1": self.vmaf_percentile_1,
            "vmaf_percentile_5": self.vmaf_percentile_5,
            "vmaf_percentile_10": self.vmaf_percentile_10,
            "vmaf_percentile_25": self.vmaf_percentile_25,
            "vmaf_percentile_50": self.vmaf_percentile_50,
            "vmaf_avg": self.vmaf_avg,
            "basename": self.basename,
            "version": self.version,
        }
        return stats

    def save(self, path):
        """
        Save stats to a file
        :param path: json file path
        :return: nun
        """
        with open(path, "w") as f:
            json.dump(self.get_dict(), f)

    def __str__(self):
        return str(self.__dict__)


class EncodersEnum(Enum):
    SVT_AV1: int = 0
    X265: int = 1
    AOMENC: int = 2
    X264: int = 3
    VP9: int = 4
    VP8: int = 5

    def __str__(self):
        return self.name

    @staticmethod
    def from_str(encoder_name: str):
        """

        :param encoder_name:
        :return:
        """
        if (
            encoder_name == "SVT-AV1"
            or encoder_name == "svt_av1"
            or encoder_name == "SVT_AV1"
        ):
            return EncodersEnum.SVT_AV1
        elif encoder_name == "x265":
            return EncodersEnum.X265
        elif encoder_name == "x264" or encoder_name == "X264":
            return EncodersEnum.X264
        elif (
            encoder_name == "aomenc"
            or encoder_name == "AOMENC"
            or encoder_name == "aom"
        ):
            return EncodersEnum.AOMENC
        elif encoder_name == "vp9" or encoder_name == "VP9" or encoder_name == "vpx_9":
            return EncodersEnum.VP9
        elif encoder_name == "vp8" or encoder_name == "VP8" or encoder_name == "vpx_8":
            return EncodersEnum.VP8
        else:
            raise ValueError(f"FATAL: Unknown encoder name: {encoder_name}")

    def supports_grain_synth(self) -> bool:
        """
        :return: True if the encoder supports grain synthesis, False otherwise
        """
        if self == EncodersEnum.SVT_AV1 or self == EncodersEnum.AOMENC:
            return True
        else:
            return False

    def get_encoder(self):
        if self == EncodersEnum.X265:
            from alabamaEncode.encoders.encoder.impl.X265 import AbstractEncoderX265

            return AbstractEncoderX265()
        elif self == EncodersEnum.SVT_AV1:
            from alabamaEncode.encoders.encoder.impl.Svtenc import AbstractEncoderSvtenc

            return AbstractEncoderSvtenc()
        elif self == EncodersEnum.AOMENC:
            from alabamaEncode.encoders.encoder.impl.Aomenc import AbstractEncoderAomEnc

            return AbstractEncoderAomEnc()
        elif self == EncodersEnum.X264:
            from alabamaEncode.encoders.encoder.impl.X264 import AbstractEncoderX264

            return AbstractEncoderX264()
        elif self == EncodersEnum.VP9:
            from alabamaEncode.encoders.encoder.impl.vp9 import EncoderVPX

            return EncoderVPX("vp9")
        elif self == EncodersEnum.VP8:
            from alabamaEncode.encoders.encoder.impl.vp9 import EncoderVPX

            return EncoderVPX("vp8")


class EncoderRateDistribution(Enum):
    VBR: int = 0  # constant bitrate
    CQ: int = 1  # constant quality
    CQ_VBV: int = 2  # constant quality with bitrate cap
    VBR_VBV: int = 3  #
