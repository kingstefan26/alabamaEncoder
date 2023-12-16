from typing import List

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.encoder_enum import EncodersEnum
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderX264(Encoder):
    def get_enum(self) -> EncodersEnum:
        return EncodersEnum.X264

    def get_version(self) -> str:
        # x264 core:164 r3095 baee400
        # Syntax: x264 [options] -o outfile infile
        return (
            run_cli(f"{get_binary('x264')} --help")
            .get_output()
            .split("\n")[0]
            .replace("x264", "")
            .strip()
        )

    def get_encode_commands(self) -> List[str]:
        if self.speed == 0:
            self.speed = 1
        self.passes = 1

        self.passes = max(self.passes, 2)

        self.speed = max(min(self.speed, 9), 0)

        if not self.hdr:
            self.bit_override = 8

        kommand = (
            f" {self.get_ffmpeg_pipe_command()} | {get_binary('x264')} - --stdin y4m "
        )

        kommand += f" --threads {self.threads} "

        kommand += f" --output-depth {self.bit_override} "
        if self.hdr:
            kommand += f" --profile high10 --hdr "
            colormatrix = self.matrix_coefficients
            if colormatrix == "bt2020-ncl":
                colormatrix = "bt2020nc"
            chromeloc = self.chroma_sample_position
            if chromeloc == "topleft":
                chromeloc = "0"
            kommand += (
                f" --colorprim {self.color_primaries} --transfer {self.transfer_characteristics} "
                f"--colormatrix {colormatrix} --chromaloc {chromeloc} "
                f"--cll {self.maximum_content_light_level},{self.maximum_frame_average_light_level}"
            )
            # if self.svt_master_display:
            #     kommand += f' --mastering-display "{self.svt_master_display}" '
        else:
            kommand += " --colorprim bt709 --transfer bt709 --colormatrix bt709 "
            kommand += " --profile high --force-cfr "

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                self.passes = 1
                kommand += f" --crf {self.crf}"
            case EncoderRateDistribution.VBR:
                kommand += f" --bitrate {self.bitrate} "
            case EncoderRateDistribution.CQ_VBV:
                kommand += f" --crf {self.crf} --bitrate {self.bitrate} "
            case EncoderRateDistribution.VBR_VBV:
                raise Exception("FATAL: rate distribution VBR_VBV not supported")

        match self.speed:
            case 9:
                kommand += " --preset ultrafast"
            case 8:
                kommand += " --preset superfast"
            case 7:
                kommand += " --preset veryfast"
            case 6:
                kommand += " --preset faster"
            case 5:
                kommand += " --preset fast"
            case 4:
                kommand += " --preset medium"
            case 3:
                kommand += " --preset slow"
            case 2:
                kommand += " --preset slower"
            case 1:
                kommand += " --preset veryslow"
            case 0:
                kommand += " --preset placebo"

        kommand += f" --tune {self.x264_tune} "

        kommand += f" --keyint {self.keyint} "

        kommand += " --stitchable "

        kommand += f" --muxer mkv "

        kommand += f" --fps {Ffmpeg.get_fps_fraction(PathAlabama(self.chunk.path))} "

        if self.passes >= 2:
            pass_1 = f'{kommand} --pass 1 --stats "{self.output_path}.stats" -o "{self.output_path}"'
            pass_2 = f'{kommand} --pass 2 --stats "{self.output_path}.stats" -o "{self.output_path}"'
            cleanups = [
                f"rm -f {self.output_path}.stats",
                f"rm -f {self.output_path}.stats.mbtree",
            ]
            return [pass_1, pass_2, cleanups]
        elif self.passes == 1:
            return [f'{kommand} -o "{self.output_path}"']

    def get_chunk_file_extension(self) -> str:
        return ".mkv"

    def supports_float_crfs(self) -> bool:
        return True

    # def parse_output_for_output(self, buffer) -> List[str]:
    #     # 42 frames: 3.60 fps, 2481.60 kb/s
    #     if buffer is None:
    #         return []
    #     match = re.search(r"\d+ frames: .+ kb/s", buffer)
    #     if match:  # check if we are past the header, also extract the string
    #         _match = re.search(
    #             r"(\d+) frames: ([0-9.]+) fps, ([0-9.]+) kb/s",
    #             match.group(0),
    #         )  # parse out the frame number, time, and bitrate
    #         return [_match.group(1), _match.group(2), _match.group(3)]
    #     else:
    #         return []
