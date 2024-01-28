from enum import Enum


class EncoderRateDistribution(Enum):
    VBR: int = 0  # variable bitrate
    CQ: int = 1  # constant quality/crf
    CQ_VBV: int = 2  # constant quality with limited bitrate
    VBR_VBV: int = 3  # variable bitrate with buffer to limit bitrate
