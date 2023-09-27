from enum import Enum

from alabamaEncode.encoders.encoder.impl.Aomenc import AbstractEncoderAomEnc
from alabamaEncode.encoders.encoder.impl.Svtenc import AbstractEncoderSvtenc
from alabamaEncode.encoders.encoder.impl.X264 import AbstractEncoderX264
from alabamaEncode.encoders.encoder.impl.X265 import AbstractEncoderX265


class EncodersEnum(Enum):
    SVT_AV1: int = 0
    X265: int = 1
    AOMENC: int = 2
    X264: int = 3

    @staticmethod
    def from_str(encoder_name: str):
        """

        :param encoder_name:
        :return:
        """
        if encoder_name == "SVT-AV1" or encoder_name == "svt_av1":
            return EncodersEnum.SVT_AV1
        elif encoder_name == "x265":
            return EncodersEnum.X265
        elif encoder_name == "x264" or encoder_name == "X264":
            return EncodersEnum.X264
        elif (
            encoder_name == "aomenc"
            or encoder_name == "AOMENC"
            or encoder_name == "aom"
        ):
            return EncodersEnum.AOMENC
        else:
            raise Exception("FATAL: Unknown encoder name: " + encoder_name)

    def supports_grain_synth(self) -> bool:
        """
        :return: True if the encoder supports grain synthesis, False otherwise
        """
        if self == EncodersEnum.SVT_AV1 or self == EncodersEnum.AOMENC:
            return True
        else:
            return False

    def get_encoder(self):
        if self == EncodersEnum.X265:
            return AbstractEncoderX265()
        elif self == EncodersEnum.SVT_AV1:
            return AbstractEncoderSvtenc()
        elif self == EncodersEnum.AOMENC:
            return AbstractEncoderAomEnc()
        elif self == EncodersEnum.X264:
            return AbstractEncoderX264()
