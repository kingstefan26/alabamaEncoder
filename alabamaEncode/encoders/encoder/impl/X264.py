from typing import List

from alabamaEncode.encoders.encoder.encoder import AbstractEncoder
from alabamaEncode.encoders.encoderMisc import EncoderRateDistribution


class AbstractEncoderX264(AbstractEncoder):
    def get_needed_path(self) -> List[str]:
        return ["ffmpeg", "ffprobe"]

    def get_encode_commands(self) -> List[str]:
        if self.speed == 0:
            self.speed = 1
        self.passes = 1

        self.passes = max(self.passes, 2)

        kommand = (
            f"ffmpeg -y {self.chunk.get_ss_ffmpeg_command_pair()} -c:v libx264 -vf {self.video_filters} "
            f"-an -sn -pix_fmt yuv420p10le -threads 1"
        )

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                kommand += f" -crf {self.crf}"
            case EncoderRateDistribution.CQ_VBV:
                kommand += f" -crf {self.crf} -maxrate {self.bitrate}k -bufsize {self.bitrate * 1.5}k"
            case EncoderRateDistribution.VBR_VBV:
                raise Exception("FATAL: rate distribution VBR_VBV not supported")
            case EncoderRateDistribution.VBR:
                kommand += f" -b:v {self.bitrate}k -maxrate {self.bitrate * 1.1}k -bufsize {self.bitrate * 1.5}k "

        match self.speed:
            case 9:
                kommand += " -preset ultrafast"
            case 8:
                kommand += " -preset superfast"
            case 7:
                kommand += " -preset veryfast"
            case 6:
                kommand += " -preset faster"
            case 5:
                kommand += " -preset fast"
            case 4:
                kommand += " -preset medium"
            case 3:
                kommand += " -preset slow"
            case 2:
                kommand += " -preset slower"
            case 1:
                kommand += " -preset veryslow"

        kommand += f" -g 9999 "

        if self.passes == 2:
            kommand += f" -passlogfile {self.output_path}.x264stat "
            return [
                f"{kommand} -pass 1 -f null /dev/null",
                f"{kommand} -pass 2 {self.output_path}",
            ]
        elif self.passes == 1:
            return [f"{kommand} {self.output_path}"]

    def get_chunk_file_extension(self) -> str:
        return ".mkv"
