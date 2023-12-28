import json
import os
import time
from typing import List

from tqdm import tqdm

from alabamaEncode.conent_analysis.chunk_analyse_pipeline_item import (
    ChunkAnalyzePipelineItem,
)
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
        return "AlabamaContext(" + str(self.dict()) + ")"

    def dict(self):
        return {
            "use_celery": self.use_celery,
            "multiprocess_workers": self.multiprocess_workers,
            "log_level": self.log_level,
            "print_analysis_logs": self.print_analysis_logs,
            "dry_run": self.dry_run,
            "temp_folder": self.temp_folder,
            "output_folder": self.output_folder,
            "output_file": self.output_file,
            "input_file": self.input_file,
            "raw_input_file": self.raw_input_file,
            "pin_to_cores": self.pin_to_cores,
            "bitrate_string": self.bitrate_string,
            "resolution_preset": self.resolution_preset,
            "crop_string": self.crop_string,
            "scale_string": self.scale_string,
            "output_height": self.output_height,
            "output_width": self.output_width,
            "find_best_bitrate": self.find_best_bitrate,
            "vbr_perchunk_optimisation": self.vbr_perchunk_optimisation,
            "ssim_db_target": self.ssim_db_target,
            "crf_bitrate_mode": self.crf_bitrate_mode,
            "bitrate_undershoot": self.bitrate_undershoot,
            "bitrate_overshoot": self.bitrate_overshoot,
            "bitrate_adjust_mode": self.bitrate_adjust_mode,
            "cutoff_bitrate": self.cutoff_bitrate,
            "max_bitrate": self.max_bitrate,
            "simple_denoise": self.simple_denoise,
            "vmaf": self.vmaf,
            "crf_model_weights": self.crf_model_weights,
            "vmaf_targeting_model": self.vmaf_targeting_model,
            "vmaf_probe_count": self.vmaf_probe_count,
            "vmaf_reference_display": self.vmaf_reference_display,
            "crf_based_vmaf_targeting": self.crf_based_vmaf_targeting,
            "vmaf_4k_model": self.vmaf_4k_model,
            "vmaf_phone_model": self.vmaf_phone_model,
            "vmaf_no_motion": self.vmaf_no_motion,
            "probe_speed_override": self.probe_speed_override,
            "ai_vmaf_targeting": self.ai_vmaf_targeting,
            "vmaf_target_representation": self.vmaf_target_representation,
            "weird_x264": self.weird_x264,
            "flag1": self.flag1,
            "flag2": self.flag2,
            "flag3": self.flag3,
            "crf_map": self.crf_map,
            "max_scene_length": self.max_scene_length,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "override_scenecache_path_check": self.override_scenecache_path_check,
            "title": self.title,
            "sub_file": self.sub_file,
            "chunk_order": self.chunk_order,
            "audio_params": self.audio_params,
            "generate_previews": self.generate_previews,
            "encoder_name": self.encoder_name,
            "encode_audio": self.encode_audio,
            "auto_crop": self.auto_crop,
            "auto_accept_autocrop": self.auto_accept_autocrop,
            "poster_url": self.poster_url,
        }

    def to_json(self):
        return json.dumps(self.dict())

    # safe version
    def from_json(self, json_str):
        try:
            parser_dict = json.loads(json_str)
        except json.decoder.JSONDecodeError:
            raise RuntimeError("Invalid JSON")
        self.__dict__ = parser_dict
        return self

    def __iter__(self):
        return self.dict().__iter__()

    use_celery: bool = False
    offload_server = ""
    multiprocess_workers: int = -1
    log_level: int = 0
    print_analysis_logs = False
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
    output_height = -1
    output_width = -1

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
    weird_x264 = False
    dynamic_vmaf_target = False
    dynamic_vmaf_target_vbr = False
    best_crfs = []

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
    poster_url = ""
    generate_previews = True
    encoder_name = "SouAV1R"
    encode_audio = True
    auto_crop = False
    auto_accept_autocrop = False

    def log(self, msg, level=0, category=""):
        if 0 < self.log_level <= level:
            tqdm.write(msg)

        if category != "":
            with open(os.path.join(self.temp_folder, f"{category}.log"), "a") as f:
                f.write(msg + "\n")
            if self.print_analysis_logs:
                tqdm.write(msg)

    def get_encoder(self) -> Encoder:
        if self.prototype_encoder is not None:
            return self.prototype_encoder.clone()
        else:
            raise RuntimeError(
                "Prototype encoder is not set, this should be impossible"
            )

    def get_output_res(self) -> List[int]:
        """
        Returns the output resolution
        """
        cache_file = os.path.join(self.temp_folder, "output_res.txt")
        if self.output_height != -1 and self.output_width != -1:
            return [self.output_width, self.output_height]
        else:
            if os.path.exists(cache_file):
                with open(cache_file) as f:
                    res = f.read()
                    output_width, output_height = res.split(",")
                    self.output_width = int(output_width)
                    self.output_height = int(output_height)
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
        with open(cache_file, "w") as f:
            f.write(f"{width},{height}")
        return [width, height]
