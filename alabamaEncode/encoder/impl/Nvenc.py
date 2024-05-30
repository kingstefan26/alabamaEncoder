from typing import List

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderNVENCH264(Encoder):

    def get_pretty_name(self) -> str:
        return "NVENC_H264"

    def get_encode_commands(self) -> List[str]:
        self.bit_override = 8  # TODO: check vaapi profile support
        vec = []
        vec.append(self.get_ffmpeg_pipe_command())
        vec.append("|")
        vec.append(get_binary("ffmpeg"))
        vec.append(" -hide_banner -y -i -")
        vec.append(f"-c:v h264_nvenc")

        vec.append(f"-g {self.keyint}")

        match self.rate_distribution:
            case EncoderRateDistribution.VBR:
                vec.append(f"-b:v {self.bitrate}k")
                vec.append("-rc 1")
            case _:
                raise NotImplementedError

        vec.append(f"-preset 18")
        vec.append(f"-spatial_aq 1")
        vec.append(f"-temporal_aq 1")
        vec.append(f"-tune 1")
        vec.append(f"-multipass 2")
        vec.append(f"-profile:v high")

        # hdr
        if self.hdr:
            vec.append(f"-color_primaries {self.color_primaries}")
            vec.append(f"-color_trc {self.transfer_characteristics}")
            vec.append(f"-colorspace {self.matrix_coefficients}")
            vec.append(f"-master_display {self.svt_master_display}")
            vec.append(
                f"-max_cll {self.maximum_content_light_level},{self.maximum_frame_average_light_level}"
            )

        # if self.bit_override == 10:
        #     vec.append('-vf "format=p010,hwupload"')
        # elif self.bit_override == 8:
        #     vec.append('-vf "format=nv12,hwupload"')

        # output
        vec.append(f'"{self.output_path}"')

        return [" ".join(vec)]

    def get_chunk_file_extension(self) -> str:
        return ".mkv"

    def get_version(self) -> str:
        return "N/A"


    def get_codec(self) -> Codec:
        return Codec.h264
