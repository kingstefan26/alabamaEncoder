from copy import copy
from typing import List

from alabamaEncode.encoders.AbstractEncoder import AbstractEncoder
from alabamaEncode.encoders.RateDiss import RateDistribution


class AbstractEncoderAomEnc(AbstractEncoder):
    def get_needed_path(self) -> List[str]:
        return ["aomenc"]

    def __init__(self):
        super().__init__()
        self.photon_noise_path = ""
        self.use_webm = False

    def get_encode_commands(self) -> List[str]:
        self.speed = min(self.speed, 9)
        encode_command = self.chunk.create_chunk_ffmpeg_pipe_command(
            crop_string=self.crop_string
        )
        encode_command += " | "
        encode_command += f"aomenc - "
        encode_command += " --quiet "
        encode_command += f'-o "{self.output_path}" '

        # 1 thread cuz we generally run this chunked
        encode_command += f"--threads=1 "

        if self.override_flags == "":
            encode_command += f"--cpu-used={self.speed} "
            encode_command += f"--bit-depth=10 "

            # STOLEN FROM ROOTATKAI IN #BENCHMARKS CUZ HE SAID ITS GOOD OR WHATEVER
            # --lag-in-frames=48 --tune-content=psy --tune=ssim --sb-size=dynamic --enable-qm=1 --qm-min=0 --qm-max=8 --row-mt=1 --disable-kf --kf-max-dist=9999 --kf-min-dist=1
            # --disable-trellis-quant=0 --arnr-maxframes=15
            encode_command += f"--lag-in-frames=48 "
            encode_command += f"--tune-content=psy "
            encode_command += " --tune=ssim "
            encode_command += f"--sb-size=dynamic "
            encode_command += f"--enable-qm=1 "
            encode_command += f"--qm-min=0 "
            encode_command += f"--qm-max=8 "
            encode_command += f"--row-mt=1 "
            encode_command += f"--disable-kf "
            encode_command += f"--kf-max-dist=9999 "
            encode_command += f"--kf-min-dist=1 "
            encode_command += f"--disable-trellis-quant=0 "
            encode_command += f"--arnr-maxframes=15 "

            if self.use_webm:
                encode_command += " --webm"
            else:
                encode_command += " --ivf"

            match self.rate_distribution:
                case RateDistribution.VBR:
                    encode_command += (
                        f" --end-usage=vbr --target-bitrate={self.bitrate}"
                    )
                case RateDistribution.CQ:
                    encode_command += f" --end-usage=q --cq-level={self.crf}"
                    self.passes = 2
                case RateDistribution.CQ_VBV:
                    if self.bitrate == -1 or self.bitrate is None:
                        encode_command += f" --end-usage=q --cq-level={self.crf}"
                    else:
                        encode_command += f" --end-usage=cq --cq-level={self.crf} --target-bitrate={self.bitrate} "

            if self.photon_noise_path == "":
                encode_command += f" --enable-dnl-denoising=1 --denoise-noise-level={self.grain_synth}"
            else:
                encode_command += f' --enable-dnl-denoising=0 --film-grain-table="{self.photon_noise_path}"'
        else:
            encode_command += self.override_flags

        if self.passes == 2:
            encode_command += f' --fpf="{self.output_path}.log"'
            encode_command += " --passes=2"

            pass2 = copy(encode_command)
            pass2 += " --pass=2"

            pass1 = copy(encode_command)
            pass1 += " --pass=1"

            return [pass1, pass2, f"rm {self.output_path}.log"]
        else:
            encode_command += " --pass=1"
            return [encode_command]

    def get_chunk_file_extension(self) -> str:
        return ".ivf"
