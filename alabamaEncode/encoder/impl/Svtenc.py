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

        if self.override_flags == "" or self.override_flags is None:
            kommand += f" --keyint {self.keyint}"

            def crf_check():
                """
                validate crf fields
                """
                if self.crf is None or self.crf == -1:
                    raise Exception("FATAL: crf is not set")
                if self.crf > 63:
                    raise Exception("FATAL: crf must be less than 63")

            kommand += f" --color-primaries {self.color_primaries}"
            kommand += f" --transfer-characteristics {self.transfer_characteristics}"

            if self.matrix_coefficients == "bt2020c":
                self.matrix_coefficients = "bt2020-cl"

            kommand += f" --matrix-coefficients {self.matrix_coefficients}"

            if self.hdr:
                kommand += f" --enable-hdr 1"
                kommand += f" --chroma-sample-position {self.chroma_sample_position}"
                kommand += (
                    f" --content-light "
                    f"{self.maximum_content_light_level},{self.maximum_frame_average_light_level}"
                )
                if self.svt_master_display != "":
                    kommand += f' --mastering-display "{self.svt_master_display}"'

            def bitrate_check():
                """
                validate bitrate fields
                """
                if self.bitrate is None or self.bitrate == -1:
                    raise Exception("FATAL: bitrate is not set")

            match self.rate_distribution:
                case EncoderRateDistribution.CQ:
                    if self.passes != 1:
                        print("WARNING: passes must be 1 for CQ, setting to 1")
                        self.passes = 1
                    crf_check()
                    kommand += f" --crf {self.crf} --rc 0"
                case EncoderRateDistribution.VBR:
                    bitrate_check()
                    kommand += f" --rc 1 --tbr {self.bitrate} --undershoot-pct 95 --overshoot-pct 10 "
                case EncoderRateDistribution.CQ_VBV:
                    bitrate_check()
                    crf_check()
                    kommand += f" --crf {self.crf} --mbr {self.bitrate}"
                case EncoderRateDistribution.VBR_VBV:
                    raise Exception("FATAL: VBR_VBV is not supported")

            kommand += f" --tune {self.svt_tune}"

            kommand += f" --pin 0"
            kommand += f" --lp {self.threads}"

            kommand += f" --aq-mode {self.svt_aq_mode}"

            if self.tile_cols != -1:
                kommand += f" --tile-columns {self.tile_cols}"
            if self.tile_rows != -1:
                kommand += f" --tile-rows {self.tile_rows}"

            if self.svt_supperres_mode != 0:
                kommand += f" --superres-mode {self.svt_supperres_mode}"
                kommand += f" --superres-denom {self.svt_superres_denom}"
                kommand += f" --superres-kf-denom {self.svt_superres_kf_denom}"
                kommand += f" --superres-qthres {self.svt_superres_qthresh}"
                kommand += f" --superres-kf-qthres {self.svt_superres_kf_qthresh}"

            if self.svt_sframe_interval > 0:
                kommand += f" --sframe-dist {self.svt_sframe_interval}"
                kommand += f" --sframe-mode {self.svt_sframe_mode}"

            if self.svt_resize_mode != 0:
                kommand += f" --resize-mode {self.svt_resize_mode}"
                kommand += f" --resize-denominator {self.svt_resize_denominator}"
                kommand += f" --resize-kf-denominator {self.svt_resize_kf_denominator}"

            if 0 <= self.grain_synth <= 50:
                kommand += f" --film-grain {self.grain_synth}"

            kommand += f" --preset {self.speed}"
            kommand += f" --film-grain-denoise 0"
            if self.qm_enabled:
                kommand += f" --qm-min {self.qm_min}"
                kommand += f" --qm-max {self.qm_max}"
                kommand += " --enable-qm 1"
            else:
                kommand += " --enable-qm 0"

            kommand += f" --enable-tf {self.svt_tf}"

            kommand += f" --enable-variance-boost {self.svt_enable_variance_boost} "
            kommand += f" --variance-boost-strength {self.svt_variance_boost_strength}"
            kommand += f" --variance-octile {self.svt_variance_octile}"
            if self.is_psy():
                kommand += f" --sharpness {self.svt_sharpness}"

        else:
            kommand += self.override_flags

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
