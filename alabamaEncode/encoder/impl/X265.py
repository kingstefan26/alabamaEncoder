from typing import List

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderX265(Encoder):

    def get_pretty_name(self) -> str:
        return "X265"

    def get_codec(self) -> Codec:
        return Codec.h265

    def get_version(self) -> str:
        return (
            run_cli(f"{get_binary('x264')} --help")
            .get_output()
            .split("\n")[0]
            .replace("x265", "")
            .strip()
        )

    def get_encode_commands(self) -> List[str]:
        if self.speed == 0:
            self.speed = 1

        kommand = (
            f" {self.get_ffmpeg_pipe_command()} | {get_binary('x265')} --input - --y4m "
        )

        if self.hdr:
            kommand += f" --output-depth {self.bit_override} "
            colormatrix = self.matrix_coefficients
            if colormatrix == "bt2020-ncl":
                colormatrix = "bt2020nc"
            chromeloc = self.chroma_sample_position
            if chromeloc == "topleft":
                chromeloc = "0"
            kommand += (
                f" --colorprim={self.color_primaries} --transfer={self.transfer_characteristics} "
                f"--colormatrix={colormatrix} --chromaloc={chromeloc} "
                f"--max-cll {self.maximum_content_light_level},{self.maximum_frame_average_light_level}"
            )
            kommand += f" --hdr10 "
            # if self.svt_master_display:
            #     kommand += f' --mastering-display "{self.svt_master_display}" '

        kommand += (
            " --wpp --ctu=64 --tu-intra-depth=2 --me=3 --subme=3 --merange=57 --rect --amp --max-merge=3 -"
            "-temporal-mvp --no-early-skip --rdpenalty=0 --no-tskip --no-tskip-fast --strong-intra-smoothing "
            "--no-lossless --no-cu-lossless --no-constrained-intra --no-fast-intra --open-gop --interlace=0 "
            "--min-keyint=24 --scenecut=40 --rc-lookahead=30 --bframes=8 "
            "--bframe-bias=0 --b-adapt=2 --ref=3 --weightp --weightb --aq-mode=2 --aq-strength=1.00 "
            "--cbqpoffs=0 --crqpoffs=0 --rd=6 --psy-rd=0.00 --psy-rdoq=0.00 --signhide --lft --sao "
            "--no-sao-non-deblock --b-pyramid --cutree --qcomp=0.60 --qpmin=0 --qpstep=4 --ipratio=1.40"
            " --pbratio=1.30 "
        )

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                kommand += f" --crf={self.crf}"
            case _:
                raise Exception(
                    f"FATAL: rate distribution {self.rate_distribution} not supported"
                )

        match self.speed:
            case 9:
                kommand += " --preset=ultrafast"
            case 8:
                kommand += " --preset=superfast"
            case 7:
                kommand += " --preset=veryfast"
            case 6:
                kommand += " --preset=faster"
            case 5:
                kommand += " --preset=fast"
            case 4:
                kommand += " --preset=medium"
            case 3:
                kommand += " --preset=slow"
            case 2:
                kommand += " --preset=slower"
            case 1:
                kommand += " --preset=veryslow"
            case 0:
                kommand += " --preset=placebo"

        kommand += f" --keyint={self.keyint} "

        if self.passes == 2:
            raise Exception("FATAL: 2 pass encoding not supported")
        elif self.passes == 1:
            hevc_file = self.output_path.replace(".mkv", ".hevc")
            remux_command = (
                f'{get_binary("mkvmerge")} -o "{self.output_path}" "{hevc_file}"'
            )
            del_commnad = f'rm "{hevc_file}"'
            return [f'{kommand} -o "{hevc_file}"', remux_command, del_commnad]

    def get_chunk_file_extension(self) -> str:
        return ".mkv"

    def supports_float_crfs(self) -> bool:
        return True
