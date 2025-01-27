from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.impl.Aomenc import EncoderAom
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.impl.VideoToolbox import EncoderAppleHEVC


def convexhull_get_crf_range(codec: Codec) -> tuple[int, int]:
    match codec:
        case Codec.av1:
            return 18, 58
        # TODO: pick other values
        case Codec.h264:
            return 10, 40
        case Codec.h265:
            return 0, 51
        case Codec.vp8:
            return 0, 63
        case Codec.vp9:
            return 0, 63
        case _:
            raise ValueError(f"FATAL: Unknown codec: {codec}")


def get_vmaf_probe_speed(encoder: Encoder, ctx=None) -> int:
    if ctx is not None:
        if ctx.vmaf_probe_speed != -1:
            return ctx.vmaf_probe_speed
    match encoder:
        case EncoderSvt():
            return 13
        case _:
            # TODO: pick other values
            return 5


def get_vmaf_probe_offset(enc: Encoder) -> int:
    match enc:
        case EncoderSvt():
            return 1
        case _:
            # TODO: pick other values
            return 0


def convexhull_get_resolutions(codec: Codec) -> list[str]:
    match codec:
        case Codec.av1:
            return ["1920:-2", "1280:-2", "960:-2", "854:-2"]
        case _:
            return ["1920:-2", "1280:-2", "960:-2", "854:-2", "768:-2", "480:-2"]


def get_crf_limits(encoder: Encoder, ctx=None) -> tuple[int, int]:
    if ctx is not None:
        if ctx.crf_limits is not None:
            return tuple(map(int, ctx.crf_limits.split(",")))
    match encoder.get_codec():
        case Codec.av1:
            match encoder:
                case EncoderSvt():
                    return 20, 35
                case _:
                    return 18, 40
        case _:
            return 12, 50


if __name__ == "__main__":
    my_enc = EncoderSvt()
    my_aom_enc = EncoderAom()

    assert get_crf_limits(my_enc), [22, 38]
    assert get_crf_limits(my_aom_enc), [18, 40]
    assert get_crf_limits(EncoderAppleHEVC()), [10, 90]


def get_vmaf_list(codec: Codec) -> list[int]:
    match codec:
        case Codec.av1:
            return [73, 78, 84, 91, 95]
        case Codec.h264:
            return [45, 55, 62, 68, 81, 87, 90, 93, 95, 96]
        case Codec.vp9:
            return [73, 78, 84, 91, 95]
        case _:
            return [73, 78, 84, 91, 95]
