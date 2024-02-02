from abc import ABC


class MetricResult(ABC):
    """
    Abstract class for metric results
    """

    fps = -1
    percentile_50 = -1
    percentile_25 = -1
    percentile_10 = -1
    percentile_5 = -1
    percentile_1 = -1
    max = -1
    min = -1
    mean = -1
    harmonic_mean = -1
    std_dev = -1
