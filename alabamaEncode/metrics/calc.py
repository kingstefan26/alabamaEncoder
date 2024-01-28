from alabamaEncode.core.path import PathAlabama
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.metric import Metrics
from alabamaEncode.metrics.ssimu2.ssimu2 import calc_ssimu2
from alabamaEncode.metrics.vmaf.vmaf import calc_vmaf
from alabamaEncode.scene.chunk import ChunkObject


def calculate_metric(
    distorted_path: PathAlabama = None,
    reference_path: PathAlabama = None,
    chunk: ChunkObject = None,
    video_filters="",
    comparison_display: ComparisonDisplayResolution = None,
    threads=1,
    options = None,
    metric: Metrics = Metrics.VMAF,
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
        case Metrics.VMAF:
            return calc_vmaf(
                chunk=_chunk,
                video_filters=video_filters,
                comparison_display_resolution=comparison_display,
                threads=threads,
                vmaf_options=options,
            )
        case Metrics.SSIMULACRA2:
            return calc_ssimu2(
                chunk=_chunk,
                video_filters=video_filters,
                comparison_display_resolution=comparison_display,
                threads=threads,
                ssimu2_options=options,
            )
        case _:
            raise NotImplementedError(f"Metric {metric} not implemented")


def get_metric_from_stats(
    stats: EncodeStats,
    statistical_representation: str = "mean",
    metric: Metrics = Metrics.VMAF,
) -> float:
    if metric != Metrics.VMAF:
        raise NotImplementedError(f"Metric {metric} not implemented")
        # TODO: implement other metrics
    match statistical_representation:
        case "mean":
            return stats.vmaf_result.mean
        case "harmonic_mean":
            return stats.vmaf_result.harmonic_mean
        case "max":
            return stats.vmaf_result.max
        case "min":
            return stats.vmaf_result.min
        case "median":
            return stats.vmaf_result.percentile_50
        case "percentile_1":
            return stats.vmaf_result.percentile_1
        case "percentile_5":
            return stats.vmaf_result.percentile_5
        case "percentile_10":
            return stats.vmaf_result.percentile_10
        case "percentile_25":
            return stats.vmaf_result.percentile_25
        case "percentile_50":
            return stats.vmaf_result.percentile_50
        case _:
            raise Exception(
                f"Unknown statistical_representation {statistical_representation}"
            )
