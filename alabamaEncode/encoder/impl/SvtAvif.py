from alabamaEncode.core.bin_utils import get_binary, verify_ffmpeg_library
from alabamaEncode.core.cli_executor import run_cli


class AvifEncoderSvtenc:
    """
    AVIF Encoder but SvtAv1 inside ffmpeg.
    """

    def __init__(self, **kwargs):
        self.DEFAULT_PARAMS = {
            "vf": " ",
            "grain_synth": 0,
            "speed": 3,
            "bit_depth": 8,
            "crf": 13,
            "passes": 1,
            "threads": 1,
        }

        self.params = {**self.DEFAULT_PARAMS, **kwargs}

    def get_params(self):
        return self.params

    def update(self, **kwargs):
        self.params = {**self.params, **kwargs}

    def get_encode_commands(self) -> str:
        verify_ffmpeg_library("libsvtav1")
        if not self.params["output_path"].endswith(".avif"):
            raise Exception("FATAL: output_path must end with .avif")

        if self.params["bit_depth"] not in (8, 10):
            raise Exception("FATAL: bit must be 8 or 10")

        pix_fmt = "yuv420p" if self.params["bit_depth"] == 8 else "yuv420p10le"

        ratebit = (
            f"-b:v {self.params['bitrate']}k"
            if self.params["bitrate"] is not None and self.params["bitrate"] != -1
            else f"-crf {self.params['crf']}"
        )

        return (
            f'{get_binary("ffmpeg")} -hide_banner -y -i "{self.params["in_path"]}" {self.params["vf"]} '
            f"-c:v libsvtav1 {ratebit} "
            f'-svtav1-params tune=0:lp={self.params["threads"]}:film-grain={self.params["grain_synth"]}'
            f' -preset {self.params["speed"]} -pix_fmt {pix_fmt} "{self.params["output_path"]}"'
        )

    def run(self):
        out = run_cli(self.get_encode_commands()).get_output()
        if (
            not os.path.exists(self.params["output_path"])
            or os.path.getsize(self.params["output_path"]) < 1
        ):
            print(self.get_encode_commands())
            raise Exception(
                f"FATAL: SVTENC ({self.get_encode_commands()}) FAILED with " + out
            )
