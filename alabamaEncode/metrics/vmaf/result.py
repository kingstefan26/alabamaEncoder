from statistics import mean


class VmafResult:
    def __init__(self, _frames, pooled_metrics, fps):
        self.pooled_metrics = pooled_metrics
        self.fps = fps
        self.vmaf_percentile_50 = -1
        self.vmaf_percentile_25 = -1
        self.vmaf_percentile_10 = -1
        self.vmaf_percentile_5 = -1
        self.vmaf_percentile_1 = -1

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
        self.vmaf_percentile_1 = vmaf_scores[int(len(vmaf_scores) * 0.01)]
        self.vmaf_percentile_5 = vmaf_scores[int(len(vmaf_scores) * 0.05)]
        self.vmaf_percentile_10 = vmaf_scores[int(len(vmaf_scores) * 0.1)]
        self.vmaf_percentile_25 = vmaf_scores[int(len(vmaf_scores) * 0.25)]
        self.vmaf_percentile_50 = vmaf_scores[int(len(vmaf_scores) * 0.5)]

        # check if pooled metrics are present
        if "vmaf" in self.pooled_metrics:
            self.mean = self.pooled_metrics["vmaf"]["mean"]
            self.harmonic_mean = self.pooled_metrics["vmaf"]["harmonic_mean"]
        else:
            self.mean = mean([x[1] for x in frames])
            self.harmonic_mean = 1 / mean([1 / x[1] for x in frames])

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
            f" prct_1={self.vmaf_percentile_1},"
            f" prct_5={self.vmaf_percentile_5},"
            f" std_dev={self.std_dev})"
        )
