from typing import List

from alabamaEncode.cli_executor import run_cli
from alabamaEncode.encoders.encoder.encoder import AbstractEncoder
from alabamaEncode.encoders.encoderMisc import EncoderRateDistribution


class AbstractEncoderX264(AbstractEncoder):
    def get_needed_path(self) -> List[str]:
        return ["ffmpeg", "ffprobe"]

    def get_version(self) -> str:
        # x264 core:164 r3095 baee400
        # Syntax: x264 [options] -o outfile infile
        return (
            run_cli("x264 --help")
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

        kommand = f" {self.get_ffmpeg_pipe_command()} | x264 - --stdin y4m "

        kommand += f" --threads {self.threads} "

        if self.hdr:
            kommand += f" --input-depth {self.bit_override} "
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
            if self.svt_master_display:
                kommand += f' --mastering-display "{self.svt_master_display}" '

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                self.passes = 1
                kommand += f" --crf {self.crf}"
            case EncoderRateDistribution.CQ_VBV:
                raise Exception("FATAL: rate distribution CQ_VBV not supported")
                # kommand += f" -crf {self.crf} -maxrate {self.bitrate}k -bufsize {self.bitrate * 1.5}k"
            case EncoderRateDistribution.VBR_VBV:
                raise Exception("FATAL: rate distribution VBR_VBV not supported")
            case EncoderRateDistribution.VBR:
                raise Exception("FATAL: rate distribution VBR not supported")
                # kommand += f" -b:v {self.bitrate}k -maxrate {self.bitrate * 1.1}k -bufsize {self.bitrate * 1.5}k "

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

        # if this is not optimal, yell at @oofer_dww on disc
        if self.speed < 5:
            pass
            # kommand += (
            #     "--no-fast-pskip --bframes 8 --scenecut 20 --aq-mode 3 --merange 48 --no-mbtree "
            #     "--non-deterministic"
            # )
            # kommand += " --no-mbtree --vbv-maxrate 20000 --vbv-bufsize 25000 --nal-hrd vbr --rc-lookahead 40 "

        kommand += f" --keyint {self.keyint} "

        if self.passes == 2:
            raise Exception("FATAL: 2 pass not supported")
            # kommand += f" -passlogfile {self.output_path}.x264stat "
            # return [
            #     f"{kommand} -pass 1 -f null /dev/null",
            #     f"{kommand} -pass 2 {self.output_path}",
            # ]

        elif self.passes == 1:
            return [f"{kommand} -o {self.output_path}"]

    def get_chunk_file_extension(self) -> str:
        return ".mkv"
