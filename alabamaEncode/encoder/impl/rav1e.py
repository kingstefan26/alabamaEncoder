from typing import List

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderRav1e(Encoder):
    def get_pretty_name(self) -> str:
        return "RAV1E"

    def get_encode_commands(self) -> List[str]:
        vec = [
            self.get_ffmpeg_pipe_command(),
            "|",
            get_binary("rav1e"),
            "-",
            f"-o {self.output_path}",
            f"-y",
            f"--threads {self.threads}",
            f"--keyint {self.keyint}",
            f"--speed {self.speed}",
            f"--photon-noise {self.grain_synth}",
        ]
        if self.tile_rows != -1:
            vec += [f"--tile-rows {self.tile_rows}"]
        if self.tile_cols != -1:
            vec += [f"--tile-cols {self.tile_cols}"]

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                vec.append(f"--quantizer {self.crf * 4}")
            case EncoderRateDistribution.VBR:
                vec.append(f"--bitrate {self.bitrate}")
            case _:
                raise NotImplementedError

        if self.hdr:
            vec.append(f"--mastering-display {self.svt_master_display}")
            vec.append(
                f"--content-light {self.maximum_content_light_level},{self.maximum_frame_average_light_level}"
            )
            vec.append(f"--primaries {self.color_primaries}")
            vec.append(f"--transfer {self.transfer_characteristics}")
            vec.append(f"--matrix {self.matrix_coefficients}")

        return [" ".join(vec)]

    def get_chunk_file_extension(self) -> str:
        return ".ivf"

    def get_version(self) -> str:
        o = run_cli(get_binary("rav1e") + " --version").get_output()
        return o.split("\n")[0].replace("rav1e ", "")


    def get_codec(self) -> Codec:
        return Codec.av1
