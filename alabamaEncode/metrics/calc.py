from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.metric import Metrics
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.metrics.vmaf.vmaf import calc_vmaf
from alabamaEncode.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject


def calculate_metric(
    distorted_path: PathAlabama = None,
    reference_path: PathAlabama = None,
    chunk: ChunkObject = None,
    video_filters="",
    comparison_display: ComparisonDisplayResolution = None,
    threads=1,
    vmaf_options: VmafOptions = None,
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
                vmaf_options=vmaf_options,
            )
        case _:
            raise NotImplementedError(f"Metric {metric} not implemented")
