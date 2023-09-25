import copy
import os
import time
from abc import abstractmethod, ABC
from typing import List

from alabamaEncode.encoders.RateDiss import RateDistribution
from alabamaEncode.encoders.encodeStats import EncodeStats, EncodeStatus
from alabamaEncode.ffmpegUtil import (
    get_video_vmeth,
    get_total_bitrate,
    doesBinaryExist,
    get_video_ssim,
)
from alabamaEncode.sceneSplit.ChunkOffset import ChunkObject
from alabamaEncode.utils.execute import syscmd


class AbstractEncoder(ABC):
    """
    owo
    """

    chunk: ChunkObject = None
    temp_folder: str
    bitrate: int = None
    crf: int = None
    current_scene_index: int
    passes: int = 2
    crop_string: str = ""
    output_path: str
    speed = 4
    first_pass_speed = 8
    threads = 1
    rate_distribution: RateDistribution = (
        RateDistribution.CQ
    )  # :param mode: 0:VBR 1:CQ 2:CQ VBV 3:VBR VBV
    qm_enabled = False
    grain_synth = 10
    qm_min = 8
    qm_max = 15
    max_bitrate = 0
    override_flags: str = ""

    bit_override = 10

    svt_bias_pct = 50  # 100 vbr like, 0 cbr like
    svt_open_gop = True
    keyint: int = 9999
    svt_sdc: int = 0
    svt_chroma_thing = -2
    svt_supperres_mode = 0
    svt_superres_denom = 8
    svt_superres_kf_denom = 8
    svt_superres_qthresh = 43
    svt_superres_kf_qthresh = 43
    svt_sframe_interval = 0
    svt_sframe_mode = 2
    svt_cli_path = "SvtAv1EncApp"
    svt_tune = 0  # tune for PsychoVisual Optimization by default
    film_grain_denoise: (0 | 1) = 1

    running_on_celery = False

    def setup(self, chunk: ChunkObject, config):
        self.update(
            chunk=chunk,
            temp_folder=config.temp_folder,
            bitrate=config.bitrate,
            crf=config.crf,
            current_scene_index=chunk.chunk_index,
            passes=config.passes,
            crop_string=config.crop_string,
            output_path=chunk.chunk_path,
            speed=config.speed,
            grain_synth=config.grain_synth,
            rate_distribution=config.rate_distribution,
            threads=config.threads,
            qm_enabled=config.qm_enabled,
            qm_min=config.qm_min,
            qm_max=config.qm_max,
            content_type=config.content_type,
            override_flags=config.override_flags,
        )

    def update(self, **kwargs):
        """
        Update the encoder with new values, with type checking
        """

        # Define a dictionary mapping attribute names to their types
        valid_attr_types = {
            "chunk": ChunkObject,
            "temp_folder": str,
            "bitrate": int,
            "crf": int,
            "current_scene_index": int,
            "passes": int,
            "crop_string": str,
            "output_path": str,
            "speed": int,
            "first_pass_speed": int,
            "grain_synth": int,
            "threads": int,
            "tune": int,
            "rate_distribution": RateDistribution,
            "qm_enabled": bool,
            "qm_min": int,
            "qm_max": int,
            "content_type": str,
            "override_flags": str,
        }

        # Loop over the dictionary
        for attr, attr_type in valid_attr_types.items():
            # If the attribute is present in kwargs
            if attr in kwargs:
                # Get the value of the attribute
                value = kwargs.get(attr)
                # If the value is not an instance of the correct type, raise an Exception
                if not isinstance(value, attr_type):
                    raise Exception(f"FATAL: {attr} must be a {attr_type.__name__}")

        # If temp_folder is in kwargs, and is not a valid directory, raise an Exception
        if "temp_folder" in kwargs and not os.path.isdir(kwargs["temp_folder"]):
            raise Exception(
                f"FATAL: temp_folder ({kwargs['temp_folder']}) must be a valid directory"
            )

        # After all checks, update the attributes
        for attr, value in kwargs.items():
            setattr(self, attr, value)

    def run(
        self, override_if_exists=True, timeout_value=-1, calculate_vmaf=False, calcualte_ssim=False
    ) -> EncodeStats:
        """
        :param override_if_exists: if false and file already exist don't do anything
        :param timeout_value: how much (in seconds) before giving up
        :param calculate_vmaf: should vmaf be included in encoded stats
        :return: stats object
        """
        stats = EncodeStats()

        for command in self.get_needed_path():
            if not doesBinaryExist(command):
                raise Exception(f"Could not find {command} in path")

        if os.path.exists(self.output_path) and not override_if_exists:
            stats.status = EncodeStatus.DONE
        else:
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

            out = []
            start = time.time()
            commands = self.get_encode_commands()

            if self.running_on_celery:
                commands.append(f"cp {self.output_path} {original_path}")
                commands.append(f"rm {self.output_path} {self.output_path}.stat")

            self.output_path = original_path

            for command in commands:
                output = syscmd(command, timeout_value=timeout_value)
                out.append(output)

            stats.time_encoding = time.time() - start

            if (
                not os.path.exists(self.output_path)
                or os.path.getsize(self.output_path) < 100
            ):
                stats.status = EncodeStatus.FAILED
                print("Encode command failed, output:")
                for o in out:
                    if isinstance(o, str):
                        o = o.replace("\x08", "")
                        print(o)
                print("Commands: ")
                for c in self.get_encode_commands():
                    print(c)

                raise Exception("FATAL: ENCODE FAILED FILE NOT FOUND OR TOO SMALL")

            stats.status = EncodeStatus.DONE

        if calculate_vmaf:
            stats.vmaf = get_video_vmeth(
                self.output_path, self.chunk, crop_string=self.crop_string
            )
        if calcualte_ssim:
            stats.ssim = get_video_ssim(self.output_path, self.chunk, crop_string=self.crop_string)

        stats.size = os.path.getsize(self.output_path) / 1000
        stats.bitrate = int(get_total_bitrate(self.output_path) / 1000)

        return stats

    @abstractmethod
    def get_encode_commands(self) -> List[str]:
        """
        Abstract method overriden by encoders.
        :return: A list of cli commands to encode, according to class fields
        """
        pass

    @abstractmethod
    def get_needed_path(self) -> List[str]:
        """
        return needed path items for encoding eg `aomenc` or `SvtAv1EncApp`
        """
        return ["ffmpeg", "ffprobe"]

    def get_ffmpeg_pipe_command(self) -> str:
        """
        return cli command that pipes a y4m stream into stdout
        """
        return self.chunk.create_chunk_ffmpeg_pipe_command(
            crop_string=self.crop_string,
            bit_depth=self.bit_override,
        )

    @abstractmethod
    def get_chunk_file_extension(self) -> str:
        return ".mkv"
