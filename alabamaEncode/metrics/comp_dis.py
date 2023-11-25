from enum import Enum


class ComparisonDisplayResolution(Enum):
    """
    Most common viewer screen resolutions
    """

    HD = 1  # 720p
    FHD = 2  # 1080p
    UHD = 3  # 4k

    @staticmethod
    def from_string(resolution: str):
        if resolution == "HD":
            return ComparisonDisplayResolution.HD
        elif resolution == "FHD":
            return ComparisonDisplayResolution.FHD
        elif resolution == "UHD":
            return ComparisonDisplayResolution.UHD
        else:
            raise ValueError("Unknown display resolution")

    def __str__(self):
        if self == ComparisonDisplayResolution.HD:
            return "1280:720"
        elif self == ComparisonDisplayResolution.FHD:
            return "1920:1080"
        elif self == ComparisonDisplayResolution.UHD:
            return "3840:2160"
        else:
            raise ValueError("Unknown display resolution")
