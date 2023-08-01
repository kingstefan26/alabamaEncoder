from enum import Enum


class RateDistribution(Enum):
    VBR: int = 0
    CQ: int = 1
    CQ_VBV: int = 2
    VBR_VBV: int = 3
