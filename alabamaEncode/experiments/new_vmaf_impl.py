from alabamaEncode.metrics.calc import calculate_metric
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.metric import Metrics
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject

if __name__ == "__main__":
    print("calcing phone vmaf with 1080p comparison display")
    a = calculate_metric(
        reference_path=(PathAlabama("/home/kokoniara/ep3_halo_test.mkv")),
        distorted_path=(PathAlabama("/home/kokoniara/SVT_ON_TOP.ivf")),
        video_filters="crop=3840:1920:0:120",
        comparison_display=ComparisonDisplayResolution.FHD,
        vmaf_options=VmafOptions(phone=True),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(a.__repr__())

    print("calcing normal vmaf with 1080p comparison display")
    a = calculate_metric(
        reference_path=(PathAlabama("/home/kokoniara/ep3_halo_test.mkv")),
        distorted_path=(PathAlabama("/home/kokoniara/SVT_ON_TOP.ivf")),
        video_filters="crop=3840:1920:0:120",
        comparison_display=ComparisonDisplayResolution.FHD,
        vmaf_options=VmafOptions(),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(a.__repr__())

    print("calcing uhd vmaf with 4k comparison display")
    a = calculate_metric(
        reference_path=(PathAlabama("/home/kokoniara/ep3_halo_test.mkv")),
        distorted_path=(PathAlabama("/home/kokoniara/SVT_ON_TOP.ivf")),
        video_filters="crop=3840:1920:0:120",
        comparison_display=ComparisonDisplayResolution.UHD,
        vmaf_options=VmafOptions(uhd=True),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(a.__repr__())

    print("Using chunk object, 720p reference display and mobile model")
    chunk = ChunkObject(path="/home/kokoniara/ep3_halo_test.mkv")
    chunk.chunk_path = "/home/kokoniara/SVT_ON_TOP.ivf"
    a = calculate_metric(
        chunk=chunk,
        video_filters="crop=3840:1920:0:120",
        comparison_display=ComparisonDisplayResolution.HD,
        vmaf_options=VmafOptions(phone=True),
        threads=10,
        metric=Metrics.VMAF,
    )
    print(a.__repr__())
