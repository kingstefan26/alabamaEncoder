"""
Stats class for encoders
"""
from enum import Enum


class EncodeStatus(Enum):
    FAILED = 0
    DONE = 1
    UNKNOWN = 2


class EncodeStats():
    def __init__(self, time_encoding: int = -1, bitrate: int = -1, vmaf: float = -1,
                 status: EncodeStatus = EncodeStatus.UNKNOWN):
        self.time_encoding = time_encoding
        self.bitrate = bitrate
        self.vmaf = vmaf
        self.status = status
