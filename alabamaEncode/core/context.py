import json
import os
import time
from typing import List, Tuple

from tqdm import tqdm

from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.kv import AlabamaKv
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.metrics.comparison_display import ComparisonDisplayResolution
from alabamaEncode.metrics.impl.vmaf import VmafOptions
from alabamaEncode.metrics.metric import Metric
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
            "throughput_scaling": self.throughput_scaling,
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
            "bitrate_undershoot": self.bitrate_undershoot,
            "bitrate_overshoot": self.bitrate_overshoot,
            "bitrate_adjust_mode": self.bitrate_adjust_mode,
            "cutoff_bitrate": self.cutoff_bitrate,
            "max_bitrate": self.max_bitrate,
            "simple_denoise": self.simple_denoise,
            "vmaf": self.vmaf,
            "probe_count": self.probe_count,
            "vmaf_reference_display": self.vmaf_reference_display,
            "crf_based_vmaf_targeting": self.crf_based_vmaf_targeting,
            "crf_limits": self.crf_limits,
            "vmaf_4k_model": self.vmaf_4k_model,
            "vmaf_phone_model": self.vmaf_phone_model,
            "vmaf_no_motion": self.vmaf_no_motion,
            "vmaf_subsample": self.vmaf_subsample,
            "vmaf_probe_speed": self.vmaf_probe_speed,
            "vmaf_target_representation": self.vmaf_target_representation,
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
            "generate_stats": self.generate_stats,
            "encoder_name": self.encoder_name,
            "encode_audio": self.encode_audio,
            "auto_crop": self.auto_crop,
            "auto_accept_autocrop": self.auto_accept_autocrop,
            "poster_url": self.poster_url,
            "statically_sized_scenes": self.statically_sized_scenes,
            "scene_merge": self.scene_merge,
            "args_tune": self.args_tune,
            "denoise_vmaf_ref": self.denoise_vmaf_ref,
        }

    def to_json(self) -> str:
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
    throughput_scaling = False
    log_level: int = 0
    print_analysis_logs = False
    dry_run: bool = False
    kv: [AlabamaKv | None] = None
    multi_res_pipeline = False

    temp_folder: str = ""
    output_folder: str = ""
    output_file: str = ""
    input_file: str = ""
    raw_input_file: str = ""
    pin_to_cores = False

    bitrate_string = None
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
    bitrate_undershoot: float = 0.90
    bitrate_overshoot: float = 2
    bitrate_adjust_mode: str = ""
    cutoff_bitrate: int = -1
    max_bitrate: int = 0
    simple_denoise = False
    args_tune = "appeal"
    calc_final_vmaf = False

    crf_limits = None
    metric_to_target = "vmaf"
    vmaf: int = 96
    vmaf_subsample = -1
    denoise_vmaf_ref = False
    probe_count = 2
    vmaf_reference_display = ""
    crf_based_vmaf_targeting = True
    vmaf_4k_model = False
    vmaf_phone_model = False
    vmaf_no_motion = False
    vmaf_probe_speed = -1
    vmaf_target_representation = "mean"
    dynamic_vmaf_target = False
    dynamic_vmaf_target_vbr = False
    best_crfs = []

    crf_map = ""

    total_chunks = -1
    max_scene_length: int = 10
    statically_sized_scenes = False
    scene_merge = False
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
    generate_previews = False
    generate_stats = False
    encoder_name = "SouAV1R"
    encode_audio = True
    auto_crop = False
    auto_accept_autocrop = False

    def log(self, msg, level=0, category=""):
        # in place so e.g. "calculated x tile rows" only shows on first run
        if category == "analyzing_content_logs":
            quiet = self.get_kv().get_global("quiet_analyzing_content_logs")
            if quiet is None or quiet is False:
                tqdm.write(msg)
            return

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

    def get_vmaf_options(self) -> VmafOptions:
        return VmafOptions(
            uhd=self.vmaf_4k_model,
            phone=self.vmaf_phone_model,
            ref=(
                ComparisonDisplayResolution.from_string(self.vmaf_reference_display)
                if self.vmaf_reference_display
                else None
            ),
            no_motion=self.vmaf_no_motion,
            denoise_refrence=self.denoise_vmaf_ref,
            subsample=self.vmaf_subsample
        )

    def get_metric_target(self) -> Tuple[Metric, float]:
        """
        Return what metric and to what degree to target based on config
        TO BE FILLED
        """
        if self.metric_to_target == "ssimu2":
            return Metric.SSIMULACRA2, self.vmaf
        return Metric.VMAF, self.vmaf

    def get_output_res(self) -> List[int]:
        """
        Returns the output resolution
        """
        cache = self.get_kv().get_global("output_res")
        if cache is not None:
            width_str, height_str = cache.split(",")
            self.output_width = int(width_str)
            self.output_height = int(height_str)
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
        self.get_kv().set_global("output_res", f"{width},{height}")

        return [width, height]

    def get_kv(self) -> AlabamaKv:
        if self.kv is None:
            self.kv = AlabamaKv(self.temp_folder)
        return self.kv

    def get_probe_file_base(self, encoded_scene_path) -> str:
        """
        A helper function to get a probe file path derived from the encoded scene path

        Examples:
        /home/test/out/temp/1.ivf -> /home/test/out/temp/1_rate_probes/
        /home/test/out/temp/42.ivf -> /home/test/out/temp/42_rate_probes/
        /home/test/out/temp/filename.ivf -> /home/test/out/temp/filename_rate_probes/
        """
        # get base file name without an extension
        file_without_extension = os.path.splitext(os.path.basename(encoded_scene_path))[
            0
        ]

        # temp folder
        path_without_file = os.path.dirname(encoded_scene_path)

        # join
        probe_folder_path = os.path.join(
            path_without_file, (file_without_extension + "_rate_probes")
        )

        # add trailing slash
        probe_folder_path += os.path.sep

        os.makedirs(probe_folder_path, exist_ok=True)

        # new file base
        return probe_folder_path

    def get_title(self):
        if self.title == "":
            return os.path.basename(self.output_file)
        return self.title
