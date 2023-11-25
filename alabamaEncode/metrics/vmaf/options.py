from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.vmaf.models import get_models


class VmafOptions:
    def __init__(
        self,
        phone=False,
        uhd=False,
        neg=False,
        ref: ComparisonDisplayResolution = None,
        no_motion=False,
    ):
        self.phone = phone
        self.uhd = uhd
        self.neg = neg
        self.ref = ref
        self.no_motion = no_motion

    def get_model(self) -> str:
        models = get_models()
        if self.no_motion:
            return f'path={models["normal_neg_nomotion"]}'
        if self.neg:
            if self.uhd:
                return f'path={models["uhd_neg"]}'
            if self.phone:
                return f'path={models["normal_neg"]}:name=phonevmaf:enable_transform'
            else:
                return f'path={models["normal_neg"]}'

        else:
            if self.uhd:
                return f'path={models["uhd"]}'
            if self.phone:
                return f'path={models["normal"]}:name=phonevmaf:enable_transform'
            else:
                return f'path={models["normal"]}'


if __name__ == "__main__":
    print(VmafOptions().get_model())
    assert VmafOptions(uhd=True).get_model() != VmafOptions().get_model()
