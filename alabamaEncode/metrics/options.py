from abc import ABC

from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution


class MetricOptions(ABC):
    ref: ComparisonDisplayResolution = None
    denoise_reference = False

    def __init__(
        self,
        **kwargs,
    ):
        if kwargs is not None:
            self.__dict__.update(kwargs)
