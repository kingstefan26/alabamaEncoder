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

    def save(self, path):
        """
        Save stats to a file
        :param path: json file path
        :return: nun
        """
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
        }
        with open(path, "w") as f:
            json.dump(stats, f)
