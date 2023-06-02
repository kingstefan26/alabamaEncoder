from enum import Enum


class EncodersEnum(Enum):
    SVT_AV1: int = 0
    X265: int = 1

    @staticmethod
    def from_str(encoder_name: str):
        """

        :param encoder_name:
        :return:
        """
        if encoder_name == 'SVT-AV1' or encoder_name == 'svt_av1':
            return EncodersEnum.SVT_AV1
        elif encoder_name == 'x265':
            return EncodersEnum.X265
        else:
            raise Exception('FATAL: Unknown encoder name: ' + encoder_name)

    def supports_grain_synth(self) -> bool:
        """
        :return: True if the encoder supports grain synthesis, False otherwise
        """
        if self == EncodersEnum.SVT_AV1:
            return True
        elif self == EncodersEnum.X265:
            return False
