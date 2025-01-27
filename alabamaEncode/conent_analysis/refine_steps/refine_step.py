from abc import abstractmethod, ABC
from typing import List


class RefineStep(ABC):
    @abstractmethod
    def __call__(self, ctx, sequence):
        pass


def get_refine_steps(ctx) -> List[RefineStep]:
    from alabamaEncode.conent_analysis.refine_steps.multires_package import (
        MutliResPackage,
    )
    from alabamaEncode.conent_analysis.refine_steps.multires_trellis import (
        MutliResTrellis,
    )

    steps = []
    if ctx.multi_res_pipeline:
        steps.append(MutliResTrellis())
        steps.append(MutliResPackage())

    return steps
