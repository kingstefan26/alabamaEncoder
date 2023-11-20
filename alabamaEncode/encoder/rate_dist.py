from enum import Enum


class EncoderRateDistribution(Enum):
    VBR: int = 0  # constant bitrate
    CQ: int = 1  # constant quality
    CQ_VBV: int = 2  # constant quality with bitrate cap
    VBR_VBV: int = 3  #
