import re

import numpy as np
from scipy.stats import hmean

from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli_parallel
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.metrics.exception import XpsnrException
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.metrics.options import MetricOptions
from alabamaEncode.metrics.result import MetricResult
from alabamaEncode.scene.chunk import ChunkObject


class XpsnrOptions(MetricOptions):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def calc_xpsnr(
    chunk: ChunkObject,
    xspnr_options: XpsnrOptions,
):
    from alabamaEncode.metrics.calculate import (
        create_content_comparison_y4m_pipes,
        cleanup_comparison_pipes,
    )

    owo = create_content_comparison_y4m_pipes(chunk=chunk, options=xspnr_options)

    reference_y4m_pipe = owo["ref_pipe"]
    distorted_y4m_pipe = owo["dist_pipe"]
    feed_reference_cli = owo["ref_command"]
    feed_distorted_cli = owo["dist_command"]

    # ffmpeg  -i ref_source.yuv -i test_video.yuv -lavfi xpsnr="stats_file=-" -f null -

    main_command = (
        f"{get_binary('ffmpeg')} -v error -i {reference_y4m_pipe} -i {distorted_y4m_pipe} "
        f'-lavfi xpsnr="stats_file=-" -f null -'
    )

    cli_results = run_cli_parallel(
        [
            feed_reference_cli,
            feed_distorted_cli,
            main_command,
        ]
    )

    cleanup_comparison_pipes(owo)

    for c in cli_results:
        try:
            c.verify()
        except RuntimeError as e:
            raise XpsnrException(
                f"Could not run xpsnr command: {e}, {[c.output for c in cli_results]}"
            )

    return XpsnrResult(cli_results[2].output)


class XpsnrResult(MetricResult):
    def __init__(self, cli_out: str):

        self.frames = []

        for line in cli_out.splitlines():
            if line.startswith("n: "):
                match = re.match(
                    r"n:\s*(\d+)\s*XPSNR y:\s*([\d.]+)\s*XPSNR u:\s*([\d.]+)\s*XPSNR v:\s*([\d.]+)",
                    line,
                )
                if match:
                    frame_num = int(match.group(1))
                    y_psnr = float(match.group(2))
                    u_psnr = float(match.group(3))
                    v_psnr = float(match.group(4))
                    self.frames.append(
                        {"frame": frame_num, "y": y_psnr, "u": u_psnr, "v": v_psnr}
                    )

        if len(self.frames) == 0:
            raise XpsnrException("No frames found")

        y_values = [frame["y"] for frame in self.frames]

        self.percentile_50 = np.percentile(y_values, 50)
        self.percentile_25 = np.percentile(y_values, 25)
        self.percentile_10 = np.percentile(y_values, 10)
        self.percentile_5 = np.percentile(y_values, 5)
        self.percentile_1 = np.percentile(y_values, 1)
        self.max = np.max(y_values)
        self.min = np.min(y_values)
        self.mean = np.mean(y_values)
        try:
            self.harmonic_mean = hmean(y_values)
        except ZeroDivisionError:
            self.harmonic_mean = -1
        self.std_dev = np.std(y_values)

    def __repr__(self):
        return (
            f"XpsnrResult(mean={self.mean}, min={self.min}, max={self.max}, "
            f"harmonic_mean={self.harmonic_mean}, std_dev={self.std_dev}, "
            f"percentile_50={self.percentile_50}, percentile_25={self.percentile_25}, "
            f"percentile_10={self.percentile_10}, percentile_5={self.percentile_5}, "
            f"percentile_1={self.percentile_1})"
        )


if __name__ == "__main__":
    print("calcing xpsnr")
    from alabamaEncode.metrics.calculate import calculate_metric

    result: XpsnrResult = calculate_metric(
        reference_path=PathAlabama("/mnt/data/objective-1-fast/MINECRAFT_60f_420.y4m"),
        distorted_path=PathAlabama(
            "/mnt/data/objective-1-fast/minecruft_test_encode_h264.mkv"
        ),
        options=XpsnrOptions(),
        metric=Metric.XPSNR,
    )

    print("h264: ", result.__repr__())

    result: XpsnrResult = calculate_metric(
        reference_path=PathAlabama("/mnt/data/objective-1-fast/MINECRAFT_60f_420.y4m"),
        distorted_path=PathAlabama(
            "/mnt/data/objective-1-fast/minecruft_test_encode_av1.mkv"
        ),
        options=XpsnrOptions(),
        metric=Metric.XPSNR,
    )

    print("av1: ", result.__repr__())
