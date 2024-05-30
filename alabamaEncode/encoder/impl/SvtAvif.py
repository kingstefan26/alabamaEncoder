import os

from alabamaEncode.core.util.bin_utils import get_binary, verify_ffmpeg_library
from alabamaEncode.core.util.cli_executor import run_cli


class AvifEncoderSvtenc:
    """
    AVIF Encoder but SvtAv1 inside ffmpeg.
    """

    vf = ""
    grain_synth = 0
    speed = 3
    bit_depth = 10
    crf = 13
    passes = 1
    bitrate = 1000
    output_path = ""
    in_path = ""

    def get_encode_commands(self) -> str:
        verify_ffmpeg_library("libsvtav1")
        if not self.output_path.endswith(".avif"):
            raise Exception("FATAL: output_path must end with .avif")

        if self.bit_depth not in (8, 10):
            raise Exception("FATAL: bit must be 8 or 10")

        pix_fmt = "yuv420p" if self.bit_depth == 8 else "yuv420p10le"

        if self.bitrate is not None and self.bitrate != -1:
            rate = f"-b:v {self.bitrate}k"
        else:
            rate = f"-crf {self.crf}"

        return (
            f'{get_binary("ffmpeg")} -hide_banner -y -i "{self.in_path}" {self.vf} '
            f"-c:v libsvtav1 {rate} "
            f"-svtav1-params tune=0:film-grain={self.grain_synth}"
            f' -preset {self.speed} -pix_fmt {pix_fmt} "{self.output_path}"'
        )

    def run(self):
        out = run_cli(self.get_encode_commands()).get_output()
        if (
            not os.path.exists(self.output_path)
            or os.path.getsize(self.output_path) < 1
        ):
            print(self.get_encode_commands())
            raise Exception(
                f"FATAL: SVTENC ({self.get_encode_commands()}) FAILED with " + out
            )
