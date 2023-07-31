from copy import copy
from typing import List

from hoeEncode.encoders.AbstractEncoder import AbstractEncoder
from hoeEncode.sceneSplit.ChunkUtil import create_chunk_ffmpeg_pipe_command_using_chunk


class AbstractEncoderAomEnc(AbstractEncoder):
    def __init__(self):
        super().__init__()
        self.use_fast_lavis = False
        self.photon_noise_path = ""
        self.extra_param = ""
        self.use_sharpness = False
        self.use_webm = False

    def get_encode_commands(self) -> List[str]:
        self.speed = min(self.speed, 9)
        encode_command = create_chunk_ffmpeg_pipe_command_using_chunk(
            in_chunk=self.chunk, crop_string=self.crop_string
        )
        encode_command += " | "
        encode_command += f"aomenc - "
        encode_command += " --quiet "
        encode_command += f'-o "{self.output_path}" '

        encode_command += f"--cpu-used={self.speed} "
        encode_command += f"--bit-depth=10 "

        # 1 thread cuz we generally run this chunked
        encode_command += f"--threads=1 "

        # disable scene detection since we do our own
        encode_command += f"--disable-kf "

        # Enable forward reference keyframes, ehh for seeking but whateva
        encode_command += " --enable-fwd-kf=1 "

        # more frames to look at = more ram eaten + more efficiency
        encode_command += f"--lag-in-frames=64 "

        # encode_command += f" --enable-cdef=0 "

        # variance-based spatial AQ.
        encode_command += f"--aq-mode=1 "

        encode_command += f" --enable-restoration=0 "

        # Quantization matrices.
        # This gives a huge compression improvement at no speed cost.
        # It should really be the default, but it's not for some reason.
        # The default qm-min and qm-max are ideal, going lower than 5 for qm-min begins to produce worse video quality.
        encode_command += f"--enable-qm=1 "

        # is a form of temporal AQ. chroma-deltaq is intended to be the same for the chroma planes, but it's currently quite naive (equivalent of x264 chroma qp offset).
        encode_command += "--deltaq-mode=2 "
        encode_command += f"--enable-chroma-deltaq=1 "
        encode_command += f"--quant-b-adapt=1 "

        # lets not go into lossless mode ok?...
        encode_command += f"--min-q=1 "

        # generally recommended content tune by the community?
        encode_command += f"--tune-content=psy "

        # Enables trellis-based quantization. This can help with detail retention.
        encode_command += f"--disable-trellis-quant=0 "

        # Reduces the strength of Alt-Ref Frame Filtering.
        # The default strength filters quite heavily.
        # We lower this to 1 to retain more detail.
        # (Some members will advocate for disabling it completely.
        # My personal opinion is that there are still issues with rate distribution when ARNR is disabled
        # that make me prefer to keep it enabled.)
        encode_command += f"--arnr-strength=1 "
        encode_command += f"--arnr-maxframes=3 "

        # 64 sized macro-blocks cuz idk
        # encode_command += f"--sb-size=64 "

        # encode_command += f'--vmaf-model-path="{self.vmaf_model}" '

        # this creates broken bitstreams so left default
        # encode_command += f"--enable-keyframe-filtering=2 "

        if self.use_webm:
            encode_command += " --webm"
        else:
            encode_command += " --ivf"

        # speed while blah blah vmaf
        encode_command += " --vmaf-resize-factor=1"

        # encode_command += ' --tune=ssim'
        if self.use_fast_lavis:
            encode_command += " --tune=lavish_fast"
        else:
            # encode_command += ' --tune=lavish_vmaf_rd'
            encode_command += " --tune=vmaf_psy_qp"
            # encode_command += ' --vmaf-quantization=1'
            # encode_command += ' --vmaf-preprocessing=1'

        if self.use_sharpness:
            encode_command += f" --sharpness=1"
            # pass

        match self.rate_distribution:
            case 0:
                # if it's a float change to int
                encode_command += f" --end-usage=vbr --target-bitrate={self.bitrate}"
            case 1:
                encode_command += f" --end-usage=q --cq-level={self.crf}"
            case 2:
                if self.bitrate == -1 or self.bitrate is None:
                    encode_command += f" --end-usage=q --cq-level={self.crf}"
                else:
                    encode_command += f" --end-usage=cq --cq-level={self.crf} --target-bitrate={self.bitrate} "
            case 3:
                # cbr
                encode_command += f" --end-usage=cbr --target-bitrate={self.bitrate} "

        if self.extra_param != "":
            encode_command += self.extra_param

        if self.photon_noise_path == "":
            encode_command += f" --enable-dnl-denoising=1 --denoise-noise-level={self.svt_grain_synth}"
        else:
            encode_command += f' --enable-dnl-denoising=0 --film-grain-table="{self.photon_noise_path}"'

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

    def extra_flags(self, param):
        self.extra_param = param
