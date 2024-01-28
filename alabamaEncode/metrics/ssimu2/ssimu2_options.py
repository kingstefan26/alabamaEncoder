from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution


class Ssimu2Options:
    def __init__(
        self,
        ref: ComparisonDisplayResolution = None,
        denoise_refrence=False,
    ):
        self.ref = ref
        self.denoise_reference = denoise_refrence
