import os
import re

from alabamaEncode.core.bin_utils import get_binary, register_bin
from alabamaEncode.core.cli_executor import run_cli, run_cli_parallel
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.metrics.calc import calculate_metric
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.metric import Metrics
from alabamaEncode.metrics.metric_exeption import Ssimu2Exception
from alabamaEncode.metrics.metric_result import MetricResult
from alabamaEncode.metrics.options import MetricOptions
from alabamaEncode.scene.chunk import ChunkObject


class Ssimu2Options(MetricOptions):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def calc_ssimu2(
    chunk: ChunkObject,
    video_filters="",
    comparison_display_resolution: ComparisonDisplayResolution = None,
    threads=1,
    ssimu2_options: Ssimu2Options = None,
):
    assert ssimu2_options is not None

    comparison_display_resolution = (
        ssimu2_options.ref
        if comparison_display_resolution is None
        else comparison_display_resolution
    )

    assert os.path.exists(chunk.path)
    assert os.path.exists(chunk.chunk_path)

    random_bit = os.urandom(16).hex()
    pipe_ref_path = f"/tmp/{os.path.basename(chunk.path)}_{random_bit}.pipe"
    pipe_dist_path = f"/tmp/{os.path.basename(chunk.chunk_path)}_{random_bit}.pipe"

    dist_filter = ""

    if comparison_display_resolution is not None:
        comparison_scaling = f"scale={comparison_display_resolution.__str__()}"

        vf = []
        if video_filters != "":
            for _filter in video_filters.split(","):
                if not re.match(r"scale=[0-9-]+:[0-9-]+", _filter):
                    vf.append(_filter)

        vf.append(comparison_scaling)
        video_filters = ",".join(vf)

        dist_filter = f" -vf {comparison_scaling} "

    if ssimu2_options.denoise_reference:
        # before scaling use the `vaguedenoiser` filter
        vf = video_filters.split(",")
        # add to the front of a list
        vf.insert(0, "vaguedenoiser")
        video_filters = ",".join(vf)

    video_filters = ",".join([f for f in video_filters.split(",") if f != ""])

    if video_filters != "":
        video_filters = f" -vf {video_filters} "

    first_pipe_command = (
        f"{get_binary('ffmpeg')} -v error -nostdin -hwaccel auto {chunk.get_ss_ffmpeg_command_pair()}"
        f" -pix_fmt yuv420p10le -an -sn -strict -1 {video_filters} -f yuv4mpegpipe - > {pipe_ref_path}"
    )
    second_pipe_command = (
        f'{get_binary("ffmpeg")} -v error -nostdin -filmgrain 0 -hwaccel auto -i "{chunk.chunk_path}" '
        f"-pix_fmt yuv420p10le -an -sn -strict -1 {dist_filter} -f yuv4mpegpipe - > {pipe_dist_path}"
    )

    # TODO: WINDOWS SUPPORT
    run_cli(f"mkfifo {pipe_ref_path}")
    run_cli(f"mkfifo {pipe_dist_path}")

    # check if both pipes are created
    assert os.path.exists(pipe_ref_path)
    assert os.path.exists(pipe_dist_path)

    main_command = f"{get_binary('ssimulacra2_rs')} video --frame-threads {threads} {pipe_ref_path} {pipe_dist_path} "

    cli_results = run_cli_parallel(
        [
            first_pipe_command,
            second_pipe_command,
            main_command,
        ]
    )

    os.remove(pipe_ref_path)
    os.remove(pipe_dist_path)

    for c in cli_results:
        try:
            c.verify()
        except RuntimeError as e:
            raise Ssimu2Exception(
                f"Could not run ssimu2 command: {e}, {[c.output for c in cli_results]}"
            )

    return Ssimu2Result(cli_results[2].output)


class Ssimu2Result(MetricResult):
    def __init__(self, cli_out: str):
        self.fps = -1
        self.percentile_50 = -1
        self.percentile_25 = -1
        self.percentile_10 = -1
        self.percentile_5 = -1
        self.percentile_1 = -1
        self.max = -1
        self.min = -1
        self.mean = -1
        self.harmonic_mean = -1
        self.std_dev = -1

        # example cli output:
        # Mean: 61.61176129
        # Median: 61.06329560
        # Std Dev: 4.19601857
        # 5th Percentile: 56.16474208
        # 95th Percentile: 69.57570546

        for line in cli_out.split("\n"):
            if "Mean" in line:
                self.mean = float(line.split(":")[1])
            if "Median" in line:
                self.percentile_50 = float(line.split(":")[1])
            if "Std Dev" in line:
                self.std_dev = float(line.split(":")[1])
            if "5th Percentile" in line:
                self.percentile_5 = float(line.split(":")[1])
            if "95th Percentile" in line:
                self.percentile_95 = float(line.split(":")[1])

    def __str__(self):
        return f"{self.mean}"

    def __repr__(self):
        return (
            f"Ssimu2Result(mean={self.mean},"
            f" prct_95={self.percentile_95},"
            f" prct_5={self.percentile_5},"
            f" std_dev={self.std_dev})"
        )


# test
if __name__ == "__main__":
    print("calcing ssimu2")
    register_bin(
        "ssimulacra2_rs",
        "/home/kokoniara/.local/opt/ssimulacra2_rs",
    )
    result: Ssimu2Result = calculate_metric(
        reference_path=PathAlabama("/mnt/data/objective-1-fast/MINECRAFT_60f_420.y4m"),
        distorted_path=PathAlabama(
            "/mnt/data/objective-1-fast/minecruft_test_encode_h264.mkv"
        ),
        options=Ssimu2Options(),
        threads=10,
        metric=Metrics.SSIMULACRA2,
    )
    print(result.mean)
    print(result.percentile_1)
    print(result.__repr__())
