from typing import List

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderAppleHEVC(Encoder):
    def get_codec(self) -> Codec:
        return Codec.h265

    def get_pretty_name(self) -> str:
        return "APPLE_H265"

    def get_encode_commands(self) -> List[str]:
        vec = [
            self.get_ffmpeg_pipe_command(),
            "|",
            get_binary("ffmpeg"),
            " -hide_banner -y -i -",
            f"-c:v hevc_videotoolbox",
            f"-allow_sw false",
            f"-g {self.keyint}",
        ]

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                vec.append(f"-q:v {self.crf}")
            case EncoderRateDistribution.VBR:
                vec.append(f"-b:v {int(self.bitrate)}k")
            case _:
                raise NotImplementedError

        if self.bit_override == 10:
            vec.append(f"-profile main10")
        else:
            vec.append(f"-profile main")

        if self.hdr:
            vec.append(f"-color_primaries {self.color_primaries}")
            vec.append(f"-color_trc {self.transfer_characteristics}")
            vec.append(f"-colorspace {self.matrix_coefficients}")
            vec.append(f"-master_display {self.svt_master_display}")
            vec.append(
                f"-max_cll {self.maximum_content_light_level},{self.maximum_frame_average_light_level}"
            )

        vec.append(f'"{self.output_path}"')

        return [" ".join(vec)]

    def get_chunk_file_extension(self) -> str:
        return ".mkv"

    def get_version(self) -> str:
        return "N/A"
