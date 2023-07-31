import copy
import os
import time
from abc import abstractmethod, ABC
from typing import List

from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encodeStats import EncodeStats, EncodeStatus
from hoeEncode.ffmpegUtil import get_video_vmeth, get_total_bitrate, doesBinaryExist
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.ChunkUtil import create_chunk_ffmpeg_pipe_command_using_chunk
from hoeEncode.utils.execute import syscmd


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
    svt_grain_synth = 10
    threads = 1
    rate_distribution: RateDistribution = RateDistribution.CQ  # :param mode: 0:VBR 1:CQ 2:CQ VBV 3:VBR VBV
    qm_enabled = False
    qm_min = 8
    qm_max = 15
    film_grain_denoise: (0 | 1) = 1
    max_bitrate = 0
    content_type = 'live_action'
    config: EncoderConfigObject = None

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
    svt_cli_path = 'SvtAv1EncApp'
    svt_tune = 0  # tune for PsychoVisual Optimization by default

    running_on_celery = False

    def eat_job_config(self, job: EncoderJob, config: EncoderConfigObject):
        self.config = copy.deepcopy(config)
        self.update(
            chunk=job.chunk,
            temp_folder=config.temp_folder,
            bitrate=config.bitrate,
            crf=config.crf,
            current_scene_index=job.chunk.chunk_index,
            passes=config.passes,
            crop_string=config.crop_string,
            output_path=job.chunk.chunk_path,
            speed=config.speed,
            svt_grain_synth=config.grain_synth,
            rate_distribution=config.rate_distribution,
            threads=config.threads,
            qm_enabled=config.qm_enabled,
            qm_min=config.qm_min,
            qm_max=config.qm_max,
            content_type=config.content_type
        )

    def update(self, **kwargs):
        """
        Update the encoder with new values, with type checking
        """
        if 'chunk' in kwargs:
            self.chunk: ChunkObject = kwargs.get('chunk')
            if not isinstance(self.chunk, ChunkObject):
                raise Exception('FATAL: chunk must be a ChunkObject')
        if 'temp_folder' in kwargs:
            self.temp_folder = kwargs.get('temp_folder')
            if not os.path.isdir(self.temp_folder):
                raise Exception(f'FATAL: temp_folder ({self.temp_folder}) must be a valid directory')
        if 'bitrate' in kwargs:
            self.bitrate = kwargs.get('bitrate')
            if not isinstance(self.bitrate, int):
                raise Exception('FATAL: bitrate must be an int')
        if 'crf' in kwargs:
            self.crf = kwargs.get('crf')
            if not isinstance(self.crf, int):
                raise Exception('FATAL: crf must be an int')
        if 'current_scene_index' in kwargs:
            self.current_scene_index = kwargs.get('current_scene_index')
            if not isinstance(self.current_scene_index, int):
                raise Exception('FATAL: current_scene_index must be an int')
        if 'passes' in kwargs:
            self.passes = kwargs.get('passes')
            if not isinstance(self.passes, int):
                raise Exception('FATAL: passes must be an int')
        if 'crop_string' in kwargs:
            self.crop_string = kwargs.get('crop_string')
            if not isinstance(self.crop_string, str):
                raise Exception('FATAL: crop_string must be a str')
        if 'output_path' in kwargs:
            self.output_path = kwargs.get('output_path')
            if not isinstance(self.output_path, str):
                raise Exception('FATAL: output_path must be a str')
        if 'speed' in kwargs:
            self.speed = kwargs.get('speed')
            if not isinstance(self.speed, int):
                raise Exception('FATAL: speed must be an int')
        if 'first_pass_speed' in kwargs:
            self.first_pass_speed = kwargs.get('first_pass_speed')
            if not isinstance(self.first_pass_speed, int):
                raise Exception('FATAL: first_pass_speed must be an int')
        if 'svt_grain_synth' in kwargs:
            self.svt_grain_synth = kwargs.get('svt_grain_synth')
            if not isinstance(self.svt_grain_synth, int):
                raise Exception('FATAL: svt_grain_synth must be an int')
        if 'threads' in kwargs:
            self.threads = kwargs.get('threads')
            if not isinstance(self.threads, int):
                raise Exception('FATAL: threads must be an int')
        if 'tune' in kwargs:
            self.svt_tune = kwargs.get('tune')
            if not isinstance(self.svt_tune, int):
                raise Exception('FATAL: tune must be an int')
        if 'rate_distribution' in kwargs:
            self.rate_distribution = kwargs.get('rate_distribution')
            if not isinstance(self.rate_distribution, RateDistribution):
                raise Exception('FATAL: rate_distribution must be an RateDistribution')
        if 'qm_enabled' in kwargs:
            self.qm_enabled = kwargs.get('qm_enabled')
            if not isinstance(self.qm_enabled, bool):
                raise Exception('FATAL: qm_enabled must be an bool')
        if 'qm_min' in kwargs:
            self.qm_min = kwargs.get('qm_min')
            if not isinstance(self.qm_min, int):
                raise Exception('FATAL: qm_min must be an int')
        if 'qm_max' in kwargs:
            self.qm_max = kwargs.get('qm_max')
            if not isinstance(self.qm_max, int):
                raise Exception('FATAL: qm_max must be an int')
        if 'content_type' in kwargs:
            self.content_type = kwargs.get('content_type')
            if not isinstance(self.content_type, str):
                raise Exception('FATAL: content_type must be an str')

    def run(self, override_if_exists=True, timeout_value=-1, calculate_vmaf=False) -> EncodeStats:
        """
        :param override_if_exists: if false and file already exist don't do anything
        :param timeout_value: how much (in seconds) before giving up
        :param calculate_vmaf: should vmaf be included in encoded stats
        :return: stats object
        """
        stats = EncodeStats()

        for command in self.get_needed_path():
            if not doesBinaryExist(command):
                raise Exception(f'Could not find {command} in path')

        if os.path.exists(self.output_path) and not override_if_exists:
            stats.status = EncodeStatus.DONE
        else:

            if self.chunk.path is None or self.chunk.path == '':
                raise Exception('FATAL: output_path is None or empty')

            if not os.path.exists(self.chunk.path):
                raise Exception('FATAL: input file does not exist')
            if self.chunk is None:
                raise Exception('FATAL: chunk is None')
            if self.chunk.chunk_index is None:
                raise Exception('FATAL: current_scene_index is None')

            original_path = copy.deepcopy(self.output_path)

            if self.running_on_celery:
                temp_celery_path = '/tmp/celery/'
                os.makedirs(temp_celery_path, exist_ok=True)
                self.output_path = f'{temp_celery_path}{self.chunk.chunk_index}{self.get_chunk_file_extension()}'

            out = []
            start = time.time()
            commands = self.get_encode_commands()

            if self.running_on_celery:
                commands.append(f'cp {self.output_path} {original_path}')
                commands.append(f'rm {self.output_path} {self.output_path}.stat')

            self.output_path = original_path

            for command in commands:
                output = syscmd(command, timeout_value=timeout_value)
                out.append(output)

            stats.time_encoding = time.time() - start

            if not os.path.exists(self.output_path) or os.path.getsize(self.output_path) < 100:
                stats.status = EncodeStatus.FAILED
                print('Encode command failed, output:')
                for o in out:
                    if isinstance(o, str):
                        o = o.replace('\x08', '')
                        print(o)
                print('Commands: ')
                for c in self.get_encode_commands():
                    print(c)

                raise Exception('FATAL: ENCODE FAILED FILE NOT FOUND OR TOO SMALL')

            stats.status = EncodeStatus.DONE

        if calculate_vmaf:
            stats.vmaf = get_video_vmeth(self.output_path, self.chunk, crop_string=self.crop_string)

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
        return ['ffmpeg', 'ffprobe']

    def get_ffmpeg_pipe_command(self) -> str:
        """
        return cli command that pipes a y4m stream into stdout
        """
        return create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=self.chunk,
                                                            crop_string=self.crop_string,
                                                            bit_depth=self.bit_override)

    def get_chunk_file_extension(self) -> str:
        return '.mkv'
