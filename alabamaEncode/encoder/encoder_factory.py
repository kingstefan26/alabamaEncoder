from typing import List

from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.impl.Aomenc import EncoderAom
from alabamaEncode.encoder.impl.Nvenc import EncoderNVENCH264
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.impl.VaapiH264 import EncoderVaapiH264
from alabamaEncode.encoder.impl.VaapiH265 import EncoderVaapiH265
from alabamaEncode.encoder.impl.VideoToolbox import EncoderAppleHEVC
from alabamaEncode.encoder.impl.X264 import EncoderX264
from alabamaEncode.encoder.impl.X265 import EncoderX265
from alabamaEncode.encoder.impl.rav1e import EncoderRav1e
from alabamaEncode.encoder.impl.vp9 import EncoderVPX

encoders = [
    EncoderX265(),
    EncoderSvt(),
    EncoderAom(),
    EncoderX264(),
    EncoderVPX("vp9"),
    EncoderVPX("vp8"),
    EncoderVaapiH265(),
    EncoderVaapiH264(),
    EncoderRav1e(),
    EncoderNVENCH264(),
    EncoderAppleHEVC()
]


def get_all_encoder_strings() -> List[str]:
    return [enc.get_pretty_name() for enc in encoders]


def get_encoder_from_string(string: str) -> Encoder:
    # special case for vpx since one class represents two encoders
    if string == "VPX_VP9":
        return EncoderVPX("vp9")

    if string == "VPX_VP8":
        return EncoderVPX("vp8")

    for enc in encoders:
        if string == enc.get_pretty_name():
            enc_class = enc.__class__
            return enc_class()

    raise Exception(f'Could not find a encoder "{string}"')


if __name__ == "__main__":
    print(get_all_encoder_strings())
    print(get_encoder_from_string("VPX_VP9"))
    print(get_encoder_from_string("X264"))
