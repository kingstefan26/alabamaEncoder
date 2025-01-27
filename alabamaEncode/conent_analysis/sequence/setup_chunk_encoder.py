from alabamaEncode.conent_analysis.chunk.final_encode_steps.dynamic_target_vmaf import (
    DynamicTargetVmaf,
)
from alabamaEncode.conent_analysis.chunk.final_encode_steps.multires_encode_finals import (
    EncodeMultiResFinals,
)


def setup_chunk_encoder(ctx, sequence):
    """
    Sets up the chunk encoder
    """

    # ugly imports here cuz "Circular import 🤓☝"
    from alabamaEncode.conent_analysis.chunk.final_encode_steps.plain import (
        PlainFinalEncode,
    )

    from alabamaEncode.conent_analysis.chunk.final_encode_steps.dynamic_target_vmaf_vbr import (
        DynamicTargetVmafVBR,
    )

    if ctx.dynamic_vmaf_target:
        ctx.chunk_encode_class = DynamicTargetVmaf()
    elif ctx.dynamic_vmaf_target_vbr:
        ctx.chunk_encode_class = DynamicTargetVmafVBR()
    elif ctx.multi_res_pipeline:
        print("Starting the multi res pipeline")
        ctx.chunk_encode_class = EncodeMultiResFinals()
    else:
        ctx.chunk_encode_class = PlainFinalEncode()

    return ctx
