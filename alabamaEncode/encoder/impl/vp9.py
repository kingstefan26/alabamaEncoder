import re
from typing import List

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderVPX(Encoder):
    def get_codec(self) -> Codec:
        return Codec.vp9

    def get_pretty_name(self) -> str:
        if self.codec == "vp9":
            return "VPX_VP9"
        elif self.codec == "vp8":
            return "VPX_VP8"


    def __init__(self, codec):
        super().__init__()
        if codec != "vp9" and codec != "vp8":
            raise ValueError(f"Invalid encoder: {codec}")
        self.codec = codec

    def get_encode_commands(self) -> List[str]:
        cli = ""
        cli += self.get_ffmpeg_pipe_command()
        cli += " | "
        vec = []
        vec.append(f"{get_binary('vpxenc')} -")
        vec.append(f"--output={self.output_path}")
        vec.append(f"--codec={self.codec}")
        vec.append(f"--ivf")
        vec.append(f"--threads={self.threads}")
        vec.append(f"--good")
        vec.append(f"--kf-max-dist={self.keyint}")
        vec.append(f"--sharpness=2")

        if self.codec == "vp9":
            self.speed = min(self.speed, 9)
            vec.append(f"--bit-depth={self.bit_override}")
            if self.bit_override == 10:
                vec.append(f"--input-bit-depth=10")
                vec.append(f"--profile=2")
            vec.append(f"--aq-mode=2")
            vec.append(f"--lag-in-frames=25")
            vec.append(f"--auto-alt-ref=1")
            vec.append(f"--row-mt=1")
            vec.append(f"--enable-tpl=1")

        elif self.codec == "vp8":
            self.speed = min(self.speed, 16)
            if self.bit_override == 10:
                print("VP8 does not support 10 bit, setting to 8 bit")
                self.bit_override = 8
            if self.hdr:
                raise ValueError("VP8 does not support HDR")

        vec.append(f"--cpu-used={self.speed}")

        match self.rate_distribution:
            case EncoderRateDistribution.VBR:
                vec.append(f"--end-usage=vbr")
                vec.append(f"--target-bitrate={self.bitrate}")
            case EncoderRateDistribution.CQ:
                vec.append(f"--end-usage=q")
                vec.append(f"--cq-level={self.crf}")
            case EncoderRateDistribution.CQ_VBV:
                vec.append(f"--end-usage=cq")
                vec.append(f"--cq-level={self.crf}")
                vec.append(f"--target-bitrate={self.bitrate}")

        if self.passes == 1:
            vec.append(f"--passes=1")
            return [cli + " ".join(vec)]
        elif self.passes == 2:
            vec.append(f"--passes=2")
            vec.append(f"--fpf={self.output_path}.log")
            commands = []
            for i in range(1, self.passes + 1):
                commands.append(
                    cli + " ".join(vec) + f" --pass={i} --fpf={self.output_path}.log"
                )
            return commands

    def get_chunk_file_extension(self) -> str:
        return ".ivf"

    def get_version(self) -> str:
        # vp9    - WebM Project VP9 Encoder v1.12.0 (default)
        match = re.search(
            r"vp9\s+-\s+WebM Project VP9 Encoder\s+(.*)",
            run_cli(f"{get_binary('vpxenc')} --help").get_output(),
        )
        if match is None:
            raise Exception("FATAL: Could not find av1 encoder version")
        return match.group(1)
