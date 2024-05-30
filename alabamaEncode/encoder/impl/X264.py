from typing import List

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderX264(Encoder):
    def get_pretty_name(self) -> str:
        return "X264"

    def get_codec(self) -> Codec:
        return Codec.h264

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
        self.speed = max(min(self.speed, 9), 0)

        if not self.hdr:
            self.bit_override = 8

        taskset = ""

        if self.pin_to_core != -1:
            taskset += f" taskset -a -c {self.pin_to_core} "

        kommand = f" {self.get_ffmpeg_pipe_command()} |{taskset}{get_binary('x264')} - --stdin y4m "

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

        if self.x264_ipratio != -1:
            kommand += f" --ipratio {self.x264_ipratio} "

        if self.x264_pbratio != -1:
            kommand += f" --pbratio {self.x264_pbratio} "

        if self.x264_aq_strength != -1:
            kommand += f" --aq-strength {self.x264_aq_strength} "

        if self.x264_merange != -1:
            kommand += f" --merange {self.x264_merange} "

        if self.x264_bframes != -1:
            kommand += f" --bframes {self.x264_bframes} "

        if self.x264_rc_lookahead != -1:
            kommand += f" --rc-lookahead {self.x264_rc_lookahead} "

        if self.x264_ref != -1:
            kommand += f" --ref {self.x264_ref} "

        if self.x264_me != "":
            kommand += f" --me {self.x264_me} "

        if self.x264_subme != -1:
            kommand += f" --subme {self.x264_subme} "

        if self.x264_non_deterministic:
            kommand += " --non-deterministic "

        if self.x264_vbv_maxrate != -1:
            kommand += f" --vbv-maxrate {self.x264_vbv_maxrate} "

        if self.x264_vbv_bufsize != -1:
            kommand += f" --vbv-bufsize {self.x264_vbv_bufsize} "

        if self.x264_slow_firstpass:
            kommand += " --slow-firstpass "

        if not self.x264_mbtree:
            kommand += " --no-mbtree "

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

        if self.x264_tune != "":
            kommand += f" --tune {self.x264_tune} "

        kommand += f" --keyint 240 "
        kommand += f" --min-keyint 240 "

        kommand += " --stitchable "

        kommand += f" --muxer mkv "

        kommand += f" --fps {Ffmpeg.get_fps_fraction(PathAlabama(self.chunk.path))} "

        if self.passes > 1 or self.x264_collect_pass or self.passes <= -2:
            kommand += f' --stats "{self.output_path}.stats" '

        if self.passes == 1 and self.x264_collect_pass:
            kommand += f" --pass 1 "

        if self.passes == 1:
            return [f'{kommand} -o "{self.output_path}"']
        elif self.passes > 1:
            com = []
            for i in range(self.passes):
                com += [f'{kommand} --pass {i + 1} -o "{self.output_path}"']

            com += [
                f"rm -f {self.output_path}.stats",
                f"rm -f {self.output_path}.stats.mbtree",
            ]

            return com
        elif self.passes == -2:
            # if passes == -2, do second pass only
            com = [f'{kommand} --pass 2 -o "{self.output_path}"']
            com += [
                f"rm -f {self.output_path}.stats",
                f"rm -f {self.output_path}.stats.mbtree",
            ]
            return com
        elif self.passes == -3:
            # if passes == -3, do second and third pass
            com = [
                f'{kommand} --pass 2 -o "{self.output_path}"',
                f'{kommand} --pass 3 -o "{self.output_path}"',
            ]
            com += [
                f"rm -f {self.output_path}.stats",
                f"rm -f {self.output_path}.stats.mbtree",
            ]
            return com

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
