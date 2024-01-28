from enum import Enum


class Codec(Enum):
    av1: int = 0
    h264: int = 1
    h265: int = 2
    vp8: int = 3
    vp9: int = 4

    def __str__(self):
        return self.name

    @staticmethod
    def from_str(codec_name: str):
        if codec_name == "av1":
            return Codec.av1
        elif codec_name == "h264":
            return Codec.h264
        elif codec_name == "h265":
            return Codec.h265
        elif codec_name == "vp8":
            return Codec.vp8
        elif codec_name == "vp9":
            return Codec.vp9
        else:
            raise ValueError(f"FATAL: Unknown codec name: {codec_name}")

    @staticmethod
    def get_all():
        return [Codec.av1, Codec.h264, Codec.h265, Codec.vp8, Codec.vp9]
