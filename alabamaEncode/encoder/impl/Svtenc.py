import re
from typing import List

from alabamaEncode.core.util.bin_utils import get_binary, check_bin
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class EncoderSvt(Encoder):
    def get_pretty_name(self) -> str:
        return "SVT_AV1"

    def get_codec(self) -> Codec:
        return Codec.av1

    def supports_grain_synth(self) -> bool:
        return True

    def get_encode_commands(self) -> List[str]:
        if (
            self.keyint == -1 or self.keyint == -2
        ) and self.rate_distribution == EncoderRateDistribution.VBR:
            print("WARNING: keyint must be set for VBR, setting to 240")
            self.keyint = 240

        kommand = ""

        if check_bin("taskset"):
            if self.pin_to_core != -1:
                kommand += f"taskset -a -c {self.pin_to_core} "

        kommand += (
            f"{self.get_ffmpeg_pipe_command()} | "
            f"{get_binary('SvtAv1EncApp')}"
            f" -i stdin"
            f" --input-depth {self.bit_override}"
            f" --progress 2 "
        )

        match self.rate_distribution:
            case EncoderRateDistribution.CQ:
                if self.passes != 1:
                    print("WARNING: passes must be 1 for CQ, setting to 1")
                    self.passes = 1
                kommand += f" --crf {self.crf} --rc 0"
            case EncoderRateDistribution.VBR:
                kommand += f" --rc 1 --tbr {self.bitrate} --undershoot-pct 95 --overshoot-pct 10 "
            case EncoderRateDistribution.CQ_VBV:
                kommand += f" --crf {self.crf} --mbr {self.bitrate}"
            case EncoderRateDistribution.VBR_VBV:
                raise Exception("FATAL: VBR_VBV is not supported")

        kommand += f" --pin 0"
        kommand += f" --lp {self.threads}"

        kommand += f" --preset {self.speed}"

        # check one be one if any flags are in the override flags, if not use the framework ones
        def add_flag(flag, value):
            nonlocal kommand
            if flag not in self.override_flags.split(" "):
                kommand += f" {flag} {value}"

        if 0 <= self.grain_synth <= 50 and "--film-grain":
            add_flag("--film-grain", self.grain_synth)

        add_flag("--color-primaries", self.color_primaries)
        add_flag("--transfer-characteristics", self.transfer_characteristics)
        add_flag("--matrix-coefficients", self.matrix_coefficients)

        if self.hdr:
            add_flag("--enable-hdr", 1)
            add_flag("--chroma-sample-position", self.chroma_sample_position)
            add_flag(
                "--content-light",
                f"{self.maximum_content_light_level},{self.maximum_frame_average_light_level}",
            )

            if self.svt_master_display != "":
                add_flag("--mastering-display", f'"{self.svt_master_display}"')

        add_flag("--tune", self.svt_tune)
        add_flag("--aq-mode", self.svt_aq_mode)
        add_flag("--tile-columns", self.tile_cols)
        add_flag("--tile-rows", self.tile_rows)
        add_flag("--keyint", self.keyint)

        if self.qm_enabled:
            add_flag("--enable-qm", 1)
            add_flag("--qm-min", self.qm_min)
            add_flag("--qm-max", self.qm_max)
        else:
            add_flag("--enable-qm", 0)

        add_flag("--film-grain-denoise", 0)
        add_flag("--enable-tf", self.svt_tf)
        add_flag("--enable-variance-boost", self.svt_enable_variance_boost)
        add_flag("--variance-boost-strength", self.svt_variance_boost_strength)
        add_flag("--variance-octile", self.svt_variance_octile)

        if self.is_psy():
            add_flag("--sharpness", self.svt_sharpness)

        if self.svt_supperres_mode != 0:
            add_flag("--superres-mode", self.svt_supperres_mode)
            add_flag("--superres-denom", self.svt_superres_denom)
            add_flag("--superres-kf-denom", self.svt_superres_kf_denom)
            add_flag("--superres-qthres", self.svt_superres_qthresh)
            add_flag("--superres-kf-qthres", self.svt_superres_kf_qthresh)

        if self.svt_sframe_interval > 0:
            add_flag("--sframe-dist", self.svt_sframe_interval)
            add_flag("--sframe-mode", self.svt_sframe_mode)

        if self.svt_resize_mode != 0:
            add_flag("--resize-mode", self.svt_resize_mode)
            add_flag("--resize-denominator", self.svt_resize_denominator)
            add_flag("--resize-kf-denominator", self.svt_resize_kf_denominator)

        if self.override_flags != "":
            kommand += " " + self.override_flags + " "

        stats_bit = ""

        if self.passes > 1:
            stats_bit = f"--stats {self.output_path}.stat"

        match self.passes:
            case 2:
                commands = [
                    f"{kommand} --pass 1 {stats_bit}",
                    f"{kommand} --pass 2 {stats_bit} -b {self.output_path}",
                    f"rm {self.output_path}.stat",
                ]
            case 1:
                commands = [f'{kommand} -b "{self.output_path}"']
            case 3:
                commands = [
                    f"{kommand} --pass 1 {stats_bit}",
                    f"{kommand} --pass 2 {stats_bit}",
                    f"{kommand} --pass 3 {stats_bit} -b {self.output_path}",
                    f"rm {self.output_path}.stat",
                ]
            case _:
                raise Exception(f"FATAL: invalid passes count {self.passes}")

        return commands

    def get_chunk_file_extension(self) -> str:
        return ".ivf"

    def get_version(self) -> str:
        # Svt[info]: -------------------------------------------
        # Svt[info]: SVT [version]:	SVT-AV1 Encoder Lib v1.7.0-2-g09df835
        o = run_cli(f"{get_binary('SvtAv1EncApp')} --version").get_output()
        return " ".join(o.split(" ")[:-1])

    def is_psy(self) -> bool:
        return "PSY" in self.get_version()

    def parse_output_for_output(self, buffer) -> List[str]:
        if buffer is None:
            return []
        match = re.search(r"Encoding frame .+\d f", buffer)
        if match:  # check if we are past the header, also extract the string
            _match = re.search(
                r"Encoding\sframe\s+([0-9]+)\s([0-9.]+)\s.+\s([0-9.]+)\sf",
                match.group(0),
            )  # parse out the frame number, time, and bitrate
            return [_match.group(1), _match.group(2), _match.group(3)]
        else:
            return []
