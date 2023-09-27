from typing import List

from alabamaEncode.encoders.RateDiss import RateDistribution
from alabamaEncode.encoders.encoder.AbstractEncoder import AbstractEncoder


class AbstractEncoderX265(AbstractEncoder):
    def get_needed_path(self) -> List[str]:
        return ["ffmpeg", "ffprobe", "x265"]

    def get_encode_commands(self) -> List[str]:
        if self.speed == 0:
            self.speed = 1
        self.passes = 1

        kommand = (
            f"ffmpeg -y {self.chunk.get_ss_ffmpeg_command_pair()} -c:v libx265 -vf {self.video_filters} "
            f"-an -sn -pix_fmt yuv420p10le"
        )

        match self.rate_distribution:
            case RateDistribution.CQ:
                kommand += f" -crf {self.crf}"
            case RateDistribution.CQ_VBV:
                raise Exception("FATAL: rate distribution not supported")
            case RateDistribution.VBR_VBV:
                raise Exception("FATAL: rate distribution not supported")
            case RateDistribution.VBR:
                raise Exception("FATAL: rate distribution not supported")

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

        def get_param_thing(pass_i=-1):
            gop = int(self.chunk.framerate * 10)
            passstring = ""
            if pass_i == 1:
                passstring = "pass=1"
            elif pass_i == 2:
                passstring = "pass=2"

            # x265 --output-depth 10 --profile main10 --me star --subme 5 --limit-modes --rect --amp
            # --max-merge 5 --no-early-skip --bframes 16 --ref 6 --rc-lookahead 60 --limit-refs 0
            # --rd 6 --psy-rdoq 1.00 --rdoq-level 2

            # Film Very Slow:
            # --crf 19.00 --no-sao
            #
            # Anime Very Slow:
            # --crf 20.00 --psy-rd 1.50 --aq-mode 3 --limit-sao

            return (
                ' -x265-params "rd=6 rdoq-level=2 psy-rdoq=1 rskip=0 limit-refs=0 tu-intra-depth=4 tu-inter-depth=4'
                " rect=1 amp=1 early-skip=0 aq-mode=3 qg-size=64 aq-strength=0.8 rc-grain=1 hme-range=28,57,92"
                f" subme=7 pools={self.threads} me=full max-merge=5 weightb=1 analyze-src-pics=1 hme=1 bframes=16"
                f" rc-lookahead=68 lookahead-slices=0 scenecut=20 ref=5 keyint={gop} {passstring}"
                f' sao=0 strong-intra-smoothing=0" -passlogfile {self.output_path}.x265stat '
            )

        if self.passes == 2:
            return [
                f"{kommand} {get_param_thing(1)} -pass 1 -f null /dev/null",
                f"{kommand} {get_param_thing(2)} -pass 2 {self.output_path}",
            ]
        elif self.passes == 1:
            return [f"{kommand} {get_param_thing()} {self.output_path}"]

    def get_chunk_file_extension(self) -> str:
        return ".mkv"
