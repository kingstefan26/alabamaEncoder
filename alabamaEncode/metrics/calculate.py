import os
import re

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.impl.ssimu2 import Ssimu2Options
from alabamaEncode.metrics.impl.vmaf import VmafOptions
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.metrics.options import MetricOptions
from alabamaEncode.scene.chunk import ChunkObject


def calculate_metric(
    options=None,
    distorted_path: PathAlabama = None,
    reference_path: PathAlabama = None,
    chunk: ChunkObject = None,
    metric: Metric = Metric.VMAF,
):
    if chunk is None:
        _chunk = ChunkObject()
        if distorted_path is None or reference_path is None:
            raise ValueError(
                "distorted_path or reference_path cannot be None when chunk is None"
            )
        _chunk.chunk_path = distorted_path.get()
        _chunk.path = reference_path.get()
    else:
        _chunk = chunk

    match metric:
        case Metric.VMAF:
            from alabamaEncode.metrics.impl.vmaf import calc_vmaf

            return calc_vmaf(
                chunk=_chunk,
                vmaf_options=options if options is not None else VmafOptions(),
            )
        case Metric.SSIMULACRA2:
            from alabamaEncode.metrics.impl.ssimu2 import calc_ssimu2

            return calc_ssimu2(
                chunk=_chunk,
                ssimu2_options=options if options is not None else Ssimu2Options(),
            )
        case _:
            raise NotImplementedError(f"Metric {metric} not implemented")


def cleanup_input_pipes(output: dict):
    if os.path.exists(output["ref_pipe"]):
        os.remove(output["ref_pipe"])
    if os.path.exists(output["dist_pipe"]):
        os.remove(output["dist_pipe"])


def get_input_pipes(chunk: ChunkObject, options: MetricOptions) -> dict:
    """
    Create two named pipes that will output distorted and reference yuv frames,
    return the pipe paths and the commands that will feed them
    """

    video_filters = options.video_filters

    assert os.path.exists(chunk.path)
    assert os.path.exists(chunk.chunk_path)

    random_bit = os.urandom(16).hex()
    pipe_ref_path = f"/tmp/{os.path.basename(chunk.path)}_{random_bit}.pipe"
    pipe_dist_path = f"/tmp/{os.path.basename(chunk.chunk_path)}_{random_bit}.pipe"

    dist_filter = ""

    if options.ref is not None:
        comparison_scaling = f"scale={options.ref.__str__()}"

        vf = []
        if video_filters != "":
            for _filter in video_filters.split(","):
                if not re.match(r"scale=[0-9-]+:[0-9-]+", _filter):
                    vf.append(_filter)

        vf.append(comparison_scaling)
        video_filters = ",".join(vf)

        dist_filter = f" -vf {comparison_scaling} "

    if options.denoise_reference:
        # before scaling use the `vaguedenoiser` filter
        vf = video_filters.split(",")
        # add to the front of a list
        vf.insert(0, "vaguedenoiser")
        video_filters = ",".join(vf)

    video_filters = ",".join([f for f in video_filters.split(",") if f != ""])

    if video_filters != "":
        video_filters = f" -vf {video_filters} "

    ref_pipe_command = (
        f"{get_binary('ffmpeg')} -v error -nostdin -hwaccel auto {chunk.get_ss_ffmpeg_command_pair()}"
        f" -pix_fmt yuv420p10le -an -sn -strict -1 {video_filters} -f yuv4mpegpipe - > {pipe_ref_path}"
    )
    dist_pipe_command = (
        f'{get_binary("ffmpeg")} -v error -nostdin -filmgrain 0 -hwaccel auto -i "{chunk.chunk_path}" '
        f"-pix_fmt yuv420p10le -an -sn -strict -1 {dist_filter} -f yuv4mpegpipe - > {pipe_dist_path}"
    )

    # TODO: WINDOWS SUPPORT
    run_cli(f"mkfifo {pipe_ref_path}")
    run_cli(f"mkfifo {pipe_dist_path}")

    # check if both pipes are created
    assert os.path.exists(pipe_ref_path)
    assert os.path.exists(pipe_dist_path)

    return {
        "ref_pipe": pipe_ref_path,
        "dist_pipe": pipe_dist_path,
        "ref_command": ref_pipe_command,
        "dist_command": dist_pipe_command,
    }


def get_metric_from_stats(
    stats: EncodeStats,
    statistical_representation: str = "mean",
) -> float:
    match statistical_representation:
        case "mean":
            return stats.metric_results.mean
        case "harmonic_mean":
            return stats.metric_results.harmonic_mean
        case "max":
            return stats.metric_results.max
        case "min":
            return stats.metric_results.min
        case "median":
            return stats.metric_results.percentile_50
        case "percentile_1":
            return stats.metric_results.percentile_1
        case "percentile_5":
            return stats.metric_results.percentile_5
        case "percentile_10":
            return stats.metric_results.percentile_10
        case "percentile_25":
            return stats.metric_results.percentile_25
        case "percentile_50":
            return stats.metric_results.percentile_50
        case _:
            raise Exception(
                f"Unknown statistical_representation {statistical_representation}"
            )
