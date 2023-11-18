from enum import Enum


class ComparisonDisplayResolution(Enum):
    """
    Most common viewer screen resolutions
    """

    HD = 1  # 720p
    FHD = 2  # 1080p
    UHD = 3  # 4k

    def __str__(self):
        if self == ComparisonDisplayResolution.HD:
            return "1280:-2"
        elif self == ComparisonDisplayResolution.FHD:
            return "1920:-2"
        elif self == ComparisonDisplayResolution.UHD:
            return "3840:-2"
        else:
            raise ValueError("Unknown display resolution")
