import copy
import os
import time
from abc import abstractmethod, ABC
from typing import List

from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.encoder.encoder_enum import EncodersEnum
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calc import calculate_metric
from alabamaEncode.metrics.metric_exeption import VmafException
from alabamaEncode.metrics.ssim.calc import get_video_ssim
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.metrics.vmaf.result import VmafResult


class Encoder(ABC):
    chunk = None
    bitrate: int = None
    crf: int = 23
    passes: int = 1
    video_filters: str = ""
    _output_path: str = None

    @property
    def output_path(self):
        if self._output_path is None:
            return self.chunk.chunk_path

        return self._output_path

    @output_path.setter
    def output_path(self, value):
        self._output_path = value

    speed = 4
    threads = 1
    rate_distribution = EncoderRateDistribution.CQ
    qm_enabled = True
    grain_synth = 3
    qm_min = 0
    qm_max = 15
    tile_cols = -1
    tile_rows = -1
    override_flags: str = ""
    pin_to_core = -1
    niceness = 0

    bit_override = 10

    svt_bias_pct = 50  # 100 vbr like, 0 cbr like
    svt_open_gop = True
    keyint: int = 999999
    svt_sdc: int = 0
    svt_chroma_thing = -2
    svt_supperres_mode = 0
    svt_superres_denom = 8
    svt_superres_kf_denom = 8
    svt_superres_qthresh = 43
    svt_superres_kf_qthresh = 43
    svt_sframe_interval = 0
    svt_sframe_mode = 2
    svt_tune = 0  # tune for PsychoVisual Optimization by default
    svt_tf = 1  # temporally filtered ALT-REF frames
    svt_overlay = 0  # enable overlays
    svt_aq_mode = 2  # 0: off, 1: flat, 2: adaptive
    film_grain_denoise: (0 | 1) = 1

    x264_tune = "film"
    x264_mbtree = True
    x264_ipratio = 1.4
    x264_pbratio = 1.3
    x264_aq_strength = -1
    x264_merange = -1
    x264_bframes = -1
    x264_rc_lookahead = -1
    x264_ref = -1
    x264_me = ""
    x264_non_deterministic = False
    x264_subme = -1
    x264_vbv_maxrate = -1
    x264_vbv_bufsize = -1
    x264_slow_firstpass = False
    x264_collect_pass = False

    color_primaries = "bt709"
    transfer_characteristics = "bt709"
    matrix_coefficients = "bt709"
    maximum_content_light_level = ""
    maximum_frame_average_light_level = ""
    chroma_sample_position = 0
    svt_master_display = ""
    hdr = False

    running_on_celery = False

    def supports_float_crfs(self) -> bool:
        return False

    def run(
        self,
        override_if_exists=True,
        timeout_value=-1,
        calculate_vmaf=False,
        calcualte_ssim=False,
        vmaf_params: VmafOptions = None,
        on_frame_encoded: callable = None,
    ) -> EncodeStats:
        """
        :param calcualte_ssim: self-explanatory
        :param calculate_vmaf: self-explanatory
        :param vmaf_params: dict of vmaf params
        :param override_if_exists: if false and file already exist don't do anything
        :param timeout_value: how much (in seconds) before giving up
        :param on_frame_encoded: callback function that gets called when a frame is encoded,
        with the following parameters: frame: the frame number bitrate: bitrate so far fps: encoding fps
        :return: EncodeStats object with scores bitrate & stuff
        """
        stats = EncodeStats()

        should_encode = False

        if not os.path.exists(self.output_path):
            should_encode = True
        elif override_if_exists:
            should_encode = True
        elif not self.chunk.is_done(quiet=True):
            should_encode = True

        if not should_encode:
            print("Skipping encode, file already exists")

        if should_encode:
            if self.chunk.path is None or self.chunk.path == "":
                raise Exception("FATAL: output_path is None or empty")

            if not os.path.exists(self.chunk.path):
                raise Exception("FATAL: input file does not exist")
            if self.chunk is None:
                raise Exception("FATAL: chunk is None")
            if self.chunk.chunk_index is None:
                raise Exception("FATAL: current_scene_index is None")

            original_path = copy.deepcopy(self.output_path)

            if self.running_on_celery:
                temp_celery_path = "/tmp/celery/"
                os.makedirs(temp_celery_path, exist_ok=True)
                self.output_path = f"{temp_celery_path}{self.chunk.chunk_index}{self.get_chunk_file_extension()}"

            cli_output = []
            start = time.time()
            commands = self.get_encode_commands()

            if self.running_on_celery:
                commands.append(f'cp {self.output_path} "{original_path}"')
                commands.append(f"rm {self.output_path} {self.output_path}.stat")

            self.output_path = original_path

            times_called = 0
            latest_frame_update = 0

            has_frame_callback = (
                self.parse_output_for_output(None) is not None
                and self.passes == 1
                and on_frame_encoded is not None
            )

            for command in commands:
                parse_func = None

                if has_frame_callback:
                    # We can report progress to a callback
                    output_buffer = ""

                    def parse(string):
                        nonlocal output_buffer
                        nonlocal times_called
                        nonlocal latest_frame_update
                        output_buffer += string
                        prog = self.parse_output_for_output(output_buffer)

                        if len(prog) > 0:
                            times_called += 1
                            # tqdm.write("FRAME ENCODED")
                            # tqdm.write(str(prog))
                            latest_frame_update = prog[0]
                            on_frame_encoded(prog[0], prog[1], prog[2])

                            output_buffer = ""

                    parse_func = parse

                cli_output.append(
                    run_cli(
                        command, timeout_value=timeout_value, on_output=parse_func
                    ).get_output()
                )

            if has_frame_callback:
                num_frames = self.chunk.get_frame_count()
                latest_frame_update = int(latest_frame_update)

                # print(
                #     f"times called {times_called}, latest frame update {latest_frame_update}, "
                #     f"total frames {num_frames}"
                # )

                if latest_frame_update != times_called:
                    for i in range(latest_frame_update - times_called):
                        on_frame_encoded(0, 0, 0)
                        times_called += 1

                # print("times called after compesnsating: ", times_called)

                # if has_frame_callback and times_called < num_frames:
                #     for i in range(num_frames - times_called):
                #         on_frame_encoded(
                #             0, 0, 0
                #         )  # if the encode didnt report any farmes to the callback,
                #         # call it manually for the rest of the frames

            stats.time_encoding = time.time() - start

            if (
                not os.path.exists(self.output_path)
                or os.path.getsize(self.output_path) < 100
            ):
                print("Encode command failed, output:")
                for o in cli_output:
                    if isinstance(o, str):
                        o = o.replace("\x08", "")
                        print(o)
                print("Commands: ")
                for c in self.get_encode_commands():
                    print(c)

                raise Exception("FATAL: ENCODE FAILED FILE NOT FOUND OR TOO SMALL")

            if stats.time_encoding < 1:
                stats.time_encoding = 1

        if calculate_vmaf:
            local_chunk = copy.deepcopy(
                self.chunk
            )  # we need seeking variables from the chunk but the path from the
            # encoder, since the encoder object might have changed the path
            local_chunk.chunk_path = self.output_path

            try:
                vmaf_result: VmafResult = calculate_metric(
                    chunk=local_chunk,
                    video_filters=self.video_filters,
                    vmaf_options=vmaf_params
                    if vmaf_params is not None
                    else VmafOptions(),
                    threads=self.threads,
                )
            except VmafException as e:
                raise Exception(f"VMAF calculation in encoder failed: {e.message}")

            stats.vmaf_result = vmaf_result
            stats.vmaf = vmaf_result.mean
            stats.vmaf_percentile_1 = vmaf_result.percentile_1
            stats.vmaf_percentile_5 = vmaf_result.percentile_5
            stats.vmaf_percentile_10 = vmaf_result.percentile_10
            stats.vmaf_percentile_25 = vmaf_result.percentile_25
            stats.vmaf_percentile_50 = vmaf_result.percentile_50
            stats.vmaf_avg = vmaf_result.mean

        if calcualte_ssim:
            ssim, ssim_db = get_video_ssim(
                self.output_path,
                self.chunk,
                video_filters=self.video_filters,
                get_db=True,
            )
            stats.ssim = ssim
            stats.ssim_db = ssim_db

        stats.size = os.path.getsize(self.output_path) / 1000
        stats.bitrate = int(
            Ffmpeg.get_total_bitrate(PathAlabama(self.output_path)) / 1000
        )

        return stats

    @abstractmethod
    def get_encode_commands(self) -> List[str]:
        """
        Abstract method overriden by encoders.
        :return: A list of cli commands to encode, according to class fields
        """
        pass

    def get_ffmpeg_pipe_command(self) -> str:
        """
        return cli command that pipes a y4m stream into stdout using the chunk object
        """
        return self.chunk.create_chunk_ffmpeg_pipe_command(
            video_filters=self.video_filters,
            bit_depth=self.bit_override,
        )

    @abstractmethod
    def get_chunk_file_extension(self) -> str:
        return ".mkv"

    @abstractmethod
    def get_version(self) -> str:
        """
        return the version of the encoder
        """
        pass

    def parse_output_for_output(self, buffer) -> [List[str] | None]:
        """
        Parse the output of the encoder and return the frame number, bitrate, and fps.
        :param buffer: The output of the encoder so far
        :return: a list of [frame, bitrate, fps], [] if no output is found, None if not implemented
        """
        return None

    @abstractmethod
    def get_enum(self) -> EncodersEnum:
        pass

    def clone(self):
        return copy.deepcopy(self)

    def supports_grain_synth(self) -> bool:
        return False
