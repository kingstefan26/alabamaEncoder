from typing import List

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderVaapiH264(Encoder):
    def get_pretty_name(self) -> str:
        return "VAAPI_H264"

    def get_codec(self) -> Codec:
        return Codec.h264

    def get_encode_commands(self) -> List[str]:
        self.bit_override = 8  # TODO: check vaapi profile support
        vec = []
        vec.append(self.get_ffmpeg_pipe_command())
        vec.append("|")
        vec.append(get_binary("ffmpeg"))
        vec.append(" -hide_banner -y -i -")
        vec.append(f"-c:v h264_vaapi")
        vec.append(f"-vaapi_device /dev/dri/renderD128")

        vec.append(f"-g {self.keyint}")

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                vec.append(f"-qp {self.crf}")
                vec.append("-rc_mode 1")
            case EncoderRateDistribution.VBR:
                vec.append(f"-b:v {self.bitrate}k")
                vec.append("-rc_mode 3")
            case _:
                raise NotImplementedError

        vec.append(f"-quality 0")
        vec.append(f"-compression_level 0")
        vec.append(f"-profile high")

        # hdr
        if self.hdr:
            vec.append(f"-color_primaries {self.color_primaries}")
            vec.append(f"-color_trc {self.transfer_characteristics}")
            vec.append(f"-colorspace {self.matrix_coefficients}")
            vec.append(f"-master_display {self.svt_master_display}")
            vec.append(
                f"-max_cll {self.maximum_content_light_level},{self.maximum_frame_average_light_level}"
            )

        if self.bit_override == 10:
            vec.append('-vf "format=p010,hwupload"')
        elif self.bit_override == 8:
            vec.append('-vf "format=nv12,hwupload"')

        # output
        vec.append(f'"{self.output_path}"')

        return [" ".join(vec)]

    def get_chunk_file_extension(self) -> str:
        return ".avi"

    def get_version(self) -> str:
        return "N/A"

