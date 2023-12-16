import os
import time
from typing import List

from tqdm import tqdm

from alabamaEncode.conent_analysis.chunk_analyse_pipeline_item import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.cli_setup.cli_args import read_args
from alabamaEncode.core.cli_setup.paths import parse_paths
from alabamaEncode.core.cli_setup.ratecontrol import parse_rd
from alabamaEncode.core.cli_setup.res_preset import parse_resolution_presets
from alabamaEncode.core.cli_setup.video_filters import parse_video_filters
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.scene.chunk import ChunkObject


class AlabamaContext:
    """
    A class to hold the configuration for an encoding instance,
    a god object (in the process of being refactored from a god object)
    """

    def __str__(self):
        return self.__dict__.__str__()

    use_celery: bool = False
    multiprocess_workers: int = -1
    log_level: int = 0
    dry_run: bool = False

    temp_folder: str = ""
    output_folder: str = ""
    output_file: str = ""
    input_file: str = ""
    raw_input_file: str = ""
    pin_to_cores = False

    bitrate_string = ""
    resolution_preset = ""
    crop_string = ""
    scale_string = ""

    chunk_analyze_chain: List[ChunkAnalyzePipelineItem] = []
    chunk_encode_class = None

    prototype_encoder: Encoder = EncoderSvt()

    find_best_bitrate = False
    vbr_perchunk_optimisation: bool = True
    ssim_db_target: float = 20
    crf_bitrate_mode: bool = False
    bitrate_undershoot: float = 0.90
    bitrate_overshoot: float = 2
    bitrate_adjust_mode: str = "chunk"
    cutoff_bitrate: int = -1
    max_bitrate: int = 0
    simple_denoise = False

    vmaf: int = 96
    crf_model_weights = "7,2,10,2,7"
    vmaf_targeting_model = "binary"
    vmaf_probe_count = 2
    vmaf_reference_display = ""
    crf_based_vmaf_targeting = True
    vmaf_4k_model = False
    vmaf_phone_model = False
    vmaf_no_motion = False
    probe_speed_override = prototype_encoder.speed
    ai_vmaf_targeting = False
    vmaf_target_representation = "mean"

    flag1: bool = False
    flag2: bool = False
    flag3: bool = False
    crf_map = ""

    max_scene_length: int = 10
    start_offset: int = -1
    end_offset: int = -1
    override_scenecache_path_check: bool = False
    title = ""
    sub_file = ""
    chunk_order = "sequential"
    audio_params = (
        "-c:a libopus -ac 2 -b:v 96k -vbr on -lfe_mix_level 0.5 -mapping_family 1"
    )
    generate_previews = True
    encoder_name = "SouAV1R"
    encode_audio = True
    auto_crop = False
    auto_accept_autocrop = False

    def log(self, msg, level=0):
        if self.log_level > 0 and level <= self.log_level:
            tqdm.write(msg)

    def get_encoder(self) -> Encoder:
        if self.prototype_encoder is not None:
            return self.prototype_encoder.clone()
        else:
            raise RuntimeError(
                "Prototype encoder is not set, this should be impossible"
            )

    output_height = -1
    output_width = -1

    def get_output_res(self) -> List[int]:
        """
        Returns the output resolution
        """
        if self.output_height != -1 and self.output_width != -1:
            return [self.output_width, self.output_height]
        enc = self.get_encoder()
        enc.chunk = ChunkObject(
            path=self.raw_input_file, first_frame_index=0, last_frame_index=2
        )
        enc.speed = 12
        enc.passes = 1
        enc.rate_distribution = EncoderRateDistribution.CQ
        enc.crf = 60
        temp_output = PathAlabama(
            f"/tmp/{time.time()}_resprobe{enc.get_chunk_file_extension()}"
        )
        enc.output_path = temp_output.get()
        enc.run()
        width = Ffmpeg.get_width(temp_output)
        height = Ffmpeg.get_height(temp_output)
        os.remove(enc.output_path)
        self.output_width = width
        self.output_height = height
        return [width, height]


def setup_context_for_standalone_usage() -> AlabamaContext:
    ctx = AlabamaContext()

    creation_pipeline = [
        read_args,
        parse_paths,
        parse_rd,
        parse_resolution_presets,
        parse_video_filters,
    ]

    for pipeline_item in creation_pipeline:
        ctx = pipeline_item(ctx)

    return ctx
