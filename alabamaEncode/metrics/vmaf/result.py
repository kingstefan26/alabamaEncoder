from statistics import mean

from alabamaEncode.metrics.metric_result import MetricResult


class VmafResult(MetricResult):
    def __init__(self, _frames=None, pooled_metrics=None, fps=None):
        if pooled_metrics is None:
            pooled_metrics = {}

        self.fps = fps

        if _frames is not None:
            frames = []
            for frame in _frames:
                if "vmaf" in frame["metrics"]:
                    frames.append([frame["frameNum"], frame["metrics"]["vmaf"]])
                else:
                    frames.append([frame["frameNum"], frame["metrics"]["phonevmaf"]])
            frames.sort(key=lambda x: x[0])
            # calc 1 5 10 25 50 percentiles
            vmaf_scores = [x[1] for x in frames]
            vmaf_scores.sort()
            self.percentile_1 = vmaf_scores[int(len(vmaf_scores) * 0.01)]
            self.percentile_5 = vmaf_scores[int(len(vmaf_scores) * 0.05)]
            self.percentile_10 = vmaf_scores[int(len(vmaf_scores) * 0.1)]
            self.percentile_25 = vmaf_scores[int(len(vmaf_scores) * 0.25)]
            self.percentile_50 = vmaf_scores[int(len(vmaf_scores) * 0.5)]

            if "vmaf" in pooled_metrics:
                self.mean = pooled_metrics["vmaf"]["mean"]
                self.harmonic_mean = pooled_metrics["vmaf"]["harmonic_mean"]
            else:
                self.mean = mean([x[1] for x in frames])
                self.harmonic_mean = 1 / mean([1 / x[1] for x in frames if x[1] != 0])

            self.max = max([x[1] for x in frames])
            self.min = min([x[1] for x in frames])

            self.std_dev = 0
            for frame in frames:
                self.std_dev += (frame[1] - self.mean) ** 2
            self.std_dev /= len(frames)
            self.std_dev **= 0.5

    def __str__(self):
        return f"{self.mean}"

    def __repr__(self):
        return (
            f"VmafResult(mean={self.mean},"
            f" fps={self.fps},"
            f" harmonic_mean={self.harmonic_mean},"
            f" prct_1={self.percentile_1},"
            f" prct_5={self.percentile_5},"
            f" std_dev={self.std_dev})"
        )
