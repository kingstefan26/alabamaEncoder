from alabamaEncode.core.util.bin_utils import get_binary, register_bin
from alabamaEncode.core.util.cli_executor import run_cli_parallel
from alabamaEncode.core.util.path import PathAlabama


from alabamaEncode.metrics.exception import Ssimu2Exception
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.metrics.options import MetricOptions
from alabamaEncode.metrics.result import MetricResult
from alabamaEncode.scene.chunk import ChunkObject


class Ssimu2Options(MetricOptions):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def calc_ssimu2(
    chunk: ChunkObject,
    ssimu2_options: Ssimu2Options,
):
    assert ssimu2_options is not None

    from alabamaEncode.metrics.calculate import get_input_pipes

    owo = get_input_pipes(chunk=chunk, options=ssimu2_options)

    ref_pipe = owo["ref_pipe"]
    dist_pipe = owo["dist_pipe"]
    ref_command = owo["ref_command"]
    dist_command = owo["dist_command"]

    main_command = f"{get_binary('ssimulacra2_rs')} video --frame-threads 4 {ref_pipe} {dist_pipe} "

    cli_results = run_cli_parallel(
        [
            ref_command,
            dist_command,
            main_command,
        ]
    )

    from alabamaEncode.metrics.calculate import cleanup_input_pipes

    cleanup_input_pipes(owo)

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
    from alabamaEncode.metrics.calculate import calculate_metric

    result: Ssimu2Result = calculate_metric(
        reference_path=PathAlabama("/mnt/data/objective-1-fast/MINECRAFT_60f_420.y4m"),
        distorted_path=PathAlabama(
            "/mnt/data/objective-1-fast/minecruft_test_encode_h264.mkv"
        ),
        options=Ssimu2Options(threads=10),
        metric=Metric.SSIMULACRA2,
    )
    print(result.mean)
    print(result.percentile_1)
    print(result.__repr__())
