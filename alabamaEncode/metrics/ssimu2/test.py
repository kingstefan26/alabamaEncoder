from alabamaEncode.core.bin_utils import register_bin
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.metrics.calc import calculate_metric
from alabamaEncode.metrics.metric import Metrics
from alabamaEncode.metrics.ssimu2.ssimu2_options import Ssimu2Options
from alabamaEncode.metrics.vmaf.result import VmafResult

if __name__ == "__main__":
    print("calcing ssimu2")
    register_bin("ssimulacra2_rs", "/home/kokoniara/.local/opt/ssimulacra2_rs")
    result: VmafResult = calculate_metric(
        reference_path=PathAlabama("/mnt/data/objective-1-fast/MINECRAFT_60f_420.y4m"),
        distorted_path=PathAlabama(
            "/mnt/data/objective-1-fast/minecruft_test_encode.mkv"
        ),
        options=Ssimu2Options(),
        threads=10,
        metric=Metrics.SSIMULACRA2,
    )
    print(result.mean)
    print(result.harmonic_mean)
    print(result.percentile_1)
    # etc with different statistical representations
    print(result.__repr__())
