from alabamaEncode.core.bin_utils import register_bin
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.metrics.calc import calculate_metric
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.metric import Metrics
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.metrics.vmaf.result import VmafResult
from alabamaEncode.scene.chunk import ChunkObject

if __name__ == "__main__":
    register_bin("vmaf", "/home/kokoniara/.local/opt/vmaf")

    reference_path = PathAlabama("/mnt/data/objective-1-fast/MINECRAFT_60f_420.y4m")
    distorted_path = PathAlabama(
        "/mnt/data/objective-1-fast/minecruft_test_encode_av1.mkv"
    )

    print("calcing phone vmaf with 1080p comparison display")
    result: VmafResult = calculate_metric(
        reference_path=reference_path,
        distorted_path=distorted_path,
        comparison_display=ComparisonDisplayResolution.FHD,
        options=VmafOptions(phone=True),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(result.mean)
    print(result.harmonic_mean)
    print(result.percentile_1)
    # etc with different statistical representations
    print(result.__repr__())

    print("calcing normal vmaf with 1080p comparison display")
    a = calculate_metric(
        reference_path=reference_path,
        distorted_path=distorted_path,
        comparison_display=ComparisonDisplayResolution.FHD,
        options=VmafOptions(),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(a.__repr__())

    print("calcing uhd vmaf with 4k comparison display")
    a = calculate_metric(
        reference_path=reference_path,
        distorted_path=distorted_path,
        comparison_display=ComparisonDisplayResolution.UHD,
        options=VmafOptions(uhd=True),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(a.__repr__())

    print("Using chunk object, 720p reference display and mobile model")
    chunk = ChunkObject(path=reference_path.path)
    chunk.chunk_path = distorted_path.path
    a = calculate_metric(
        chunk=chunk,
        comparison_display=ComparisonDisplayResolution.HD,
        options=VmafOptions(phone=True),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(a.__repr__())
