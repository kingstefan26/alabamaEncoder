import json

from alabamaEncode.metrics.vmaf.result import VmafResult


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
        ssim_db: float = -1,
        size: int = -1,
        total_fps: int = -1,
        target_miss_proc: int = -1,
        rate_search_time: int = -1,
        chunk_index: int = -1,
        basename: str = "",
        version: str = "",
        vmaf_result: VmafResult = None,
        length_frames: int = -1,
    ):
        self.time_encoding = time_encoding
        self.bitrate = bitrate
        self.vmaf = vmaf
        self.ssim = ssim
        self.ssim_db = ssim_db
        self.size = size  # size in kilo Bytes
        self.total_fps = total_fps
        self.target_miss_proc = target_miss_proc
        self.rate_search_time = rate_search_time
        self.chunk_index = chunk_index
        self.basename = basename
        self.version = version
        self.vmaf_result = vmaf_result or VmafResult()
        self.length_frames = length_frames

    def __dict__(self):
        return {
            "time_encoding": self.time_encoding,
            "bitrate": self.bitrate,
            "chunk_index": self.chunk_index,
            "length_frames": self.length_frames,
            "vmaf": self.vmaf_result.mean,
            "ssim": self.ssim,
            "ssim_db": self.ssim_db,
            "size": self.size,
            "total_fps": self.total_fps,
            "target_miss_proc": self.target_miss_proc,
            "rate_search_time": self.rate_search_time,
            "vmaf_percentile_1": self.vmaf_result.percentile_1,
            "vmaf_percentile_5": self.vmaf_result.percentile_5,
            "vmaf_percentile_10": self.vmaf_result.percentile_10,
            "vmaf_percentile_25": self.vmaf_result.percentile_25,
            "vmaf_percentile_50": self.vmaf_result.percentile_50,
            "vmaf_avg": self.vmaf_result.mean,
            "basename": self.basename,
            "version": self.version,
        }

    def save(self, path):
        """
        Save stats to a file
        :param path: json file path
        :return: nun
        """
        with open(path, "w") as f:
            json.dump(self.__dict__(), f)

    def __str__(self):
        return str(self.__dict__)