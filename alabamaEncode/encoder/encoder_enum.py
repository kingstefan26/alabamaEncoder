from enum import Enum


class EncodersEnum(Enum):
    SVT_AV1: int = 0
    X265: int = 1
    AOMENC: int = 2
    X264: int = 3
    VP9: int = 4
    VP8: int = 5

    def __str__(self):
        return self.name

    @staticmethod
    def from_str(encoder_name: str):
        """

        :param encoder_name:
        :return:
        """
        if (
            encoder_name == "SVT-AV1"
            or encoder_name == "svt_av1"
            or encoder_name == "SVT_AV1"
        ):
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
        elif encoder_name == "vp9" or encoder_name == "VP9" or encoder_name == "vpx_9":
            return EncodersEnum.VP9
        elif encoder_name == "vp8" or encoder_name == "VP8" or encoder_name == "vpx_8":
            return EncodersEnum.VP8
        else:
            raise ValueError(f"FATAL: Unknown encoder name: {encoder_name}")

    def get_encoder(self):
        if self == EncodersEnum.X265:
            from alabamaEncode.encoder.impl.X265 import EncoderX265

            return EncoderX265()
        elif self == EncodersEnum.SVT_AV1:
            from alabamaEncode.encoder.impl.Svtenc import EncoderSvt

            return EncoderSvt()
        elif self == EncodersEnum.AOMENC:
            from alabamaEncode.encoder.impl.Aomenc import EncoderAom

            return EncoderAom()
        elif self == EncodersEnum.X264:
            from alabamaEncode.encoder.impl.X264 import EncoderX264

            return EncoderX264()
        elif self == EncodersEnum.VP9:
            from alabamaEncode.encoder.impl.vp9 import EncoderVPX

            return EncoderVPX("vp9")
        elif self == EncodersEnum.VP8:
            from alabamaEncode.encoder.impl.vp9 import EncoderVPX

            return EncoderVPX("vp8")
