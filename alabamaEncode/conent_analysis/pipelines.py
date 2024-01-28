from typing import List

from alabamaEncode.conent_analysis.chunk.analyze_steps.multires_encode_candidates import (
    EncodeMultiResCandidates,
)
from alabamaEncode.conent_analysis.chunk.final_encode_steps.dynamic_target_vmaf import (
    DynamicTargetVmaf,
)
from alabamaEncode.conent_analysis.chunk.final_encode_steps.multires_encode_finals import (
    EncodeMultiResFinals,
)
from alabamaEncode.conent_analysis.refine_step import RefineStep
from alabamaEncode.conent_analysis.refine_steps.multires_package import MutliResPackage
from alabamaEncode.conent_analysis.refine_steps.multires_trellis import MutliResTrellis


def setup_chunk_analyze_chain(ctx, sequence):
    """
    Sets up the chunk analyze chain
    """
    from alabamaEncode.conent_analysis.chunk.analyze_steps.capped_crf import CapedCrf
    from alabamaEncode.conent_analysis.chunk.analyze_steps.manual_crf import (
        CrfIndexesMap,
    )
    from alabamaEncode.conent_analysis.chunk.analyze_steps.optimised_vbr import (
        VbrPerChunkOptimised,
    )
    from alabamaEncode.conent_analysis.chunk.analyze_steps.per_scene_grain import (
        GrainSynth,
    )
    from alabamaEncode.conent_analysis.chunk.analyze_steps.plain_crf import PlainCrf
    from alabamaEncode.conent_analysis.chunk.analyze_steps.plain_vbr import PlainVbr
    from alabamaEncode.conent_analysis.chunk.analyze_steps.target_vmaf import TargetVmaf

    ctx.chunk_analyze_chain = []

    # grain synth, per chunk parameters etc.
    if ctx.prototype_encoder.grain_synth == -2:
        ctx.chunk_analyze_chain.append(GrainSynth())

    # setting up rate control, adaptive or not
    if ctx.weird_x264:
        ctx.chunk_analyze_chain.append(PlainCrf())
    elif ctx.bitrate_adjust_mode == "chunk":
        ctx.chunk_analyze_chain.append(VbrPerChunkOptimised())
    elif ctx.dynamic_vmaf_target:
        print("Using dynamic vmaf targeting")
        ctx.chunk_analyze_chain.append(PlainCrf())
    elif ctx.dynamic_vmaf_target_vbr:
        print("Using dynamic vmaf targeting with vbr")
        ctx.chunk_analyze_chain.append(PlainVbr())
    elif ctx.multi_res_pipeline:
        ctx.chunk_analyze_chain.append(EncodeMultiResCandidates())
    elif ctx.crf_map != "":
        ctx.chunk_analyze_chain.append(CrfIndexesMap(ctx.crf_map))
    elif ctx.flag1 is True:
        ctx.chunk_analyze_chain.append(PlainCrf())
    elif (
        ctx.crf_based_vmaf_targeting is True
        and ctx.ai_vmaf_targeting is False
        and ctx.multi_res_pipeline is False
    ):
        ctx.chunk_analyze_chain.append(TargetVmaf())
    elif ctx.crf_bitrate_mode or ctx.ai_vmaf_targeting:
        ctx.chunk_analyze_chain.append(CapedCrf())
    elif ctx.prototype_encoder.crf != -1:
        ctx.chunk_analyze_chain.append(PlainCrf())
    else:
        ctx.chunk_analyze_chain.append(PlainVbr())

    if len(ctx.chunk_analyze_chain) == 0:
        raise Exception("Failed to Create the analyze steps in analyzer_factory")

    return ctx


def setup_chunk_encoder(ctx, sequence):
    """
    Sets up the chunk encoder
    """

    # ugly imports here cuz "Circular import 🤓☝"
    from alabamaEncode.conent_analysis.chunk.final_encode_steps.ai_targeted_vmaf import (
        AiTargetedVmafFinalEncode,
    )
    from alabamaEncode.conent_analysis.chunk.final_encode_steps.capped_crf_encode import (
        WeridCapedCrfFinalEncode,
    )
    from alabamaEncode.conent_analysis.chunk.final_encode_steps.plain import (
        PlainFinalEncode,
    )

    from alabamaEncode.conent_analysis.chunk.final_encode_steps.weirdX264 import (
        TargetX264,
    )

    from alabamaEncode.conent_analysis.chunk.final_encode_steps.dynamic_target_vmaf_vbr import (
        DynamicTargetVmafVBR,
    )

    if ctx.weird_x264:
        ctx.chunk_encode_class = TargetX264()
    elif ctx.flag1:
        ctx.chunk_encode_class = WeridCapedCrfFinalEncode()
    elif ctx.ai_vmaf_targeting:
        ctx.chunk_encode_class = AiTargetedVmafFinalEncode()
    elif ctx.dynamic_vmaf_target:
        ctx.chunk_encode_class = DynamicTargetVmaf()
    elif ctx.dynamic_vmaf_target_vbr:
        ctx.chunk_encode_class = DynamicTargetVmafVBR()
    elif ctx.multi_res_pipeline:
        print("Starting the multi res pipeline")
        ctx.chunk_encode_class = EncodeMultiResFinals()
    else:
        ctx.chunk_encode_class = PlainFinalEncode()

    return ctx


def get_refine_steps(ctx) -> List[RefineStep]:
    steps = []
    if ctx.multi_res_pipeline:
        steps.append(MutliResTrellis())
        steps.append(MutliResPackage())

    return steps


async def run_sequence_pipeline(ctx, sequence):
    from alabamaEncode.conent_analysis.sequence.autocrop import do_autocrop
    from alabamaEncode.conent_analysis.sequence.args_tune import (
        tune_args_for_fdlty_or_apl,
    )
    from alabamaEncode.conent_analysis.sequence.denoise_filtering import setup_denoise
    from alabamaEncode.conent_analysis.sequence.encoding_tiles import setup_tiles
    from alabamaEncode.conent_analysis.sequence.ideal_crf import (
        setup_ideal_crf_weighted,
    )
    from alabamaEncode.conent_analysis.sequence.scrape_hdr_meta import (
        scrape_hdr_metadata,
    )
    from alabamaEncode.conent_analysis.sequence.sequence_autograin import (
        setup_autograin,
    )
    from alabamaEncode.conent_analysis.sequence.taget_ssimdb import setup_ssimdb_target
    from alabamaEncode.conent_analysis.sequence.target_bitrate_optimisation import (
        setup_ideal_bitrate,
    )
    from alabamaEncode.conent_analysis.sequence.x264_tune import get_ideal_x264_tune

    pipeline = [
        setup_chunk_analyze_chain,
        setup_chunk_encoder,
        scrape_hdr_metadata,
        tune_args_for_fdlty_or_apl,
        do_autocrop,
        setup_tiles,
        setup_denoise,
        setup_autograin,
        setup_ideal_crf_weighted,
        setup_ideal_bitrate,
        setup_ssimdb_target,
        get_ideal_x264_tune,
    ]

    for func in pipeline:
        # if async run awaits, if not run normally
        ctx = (
            await func(ctx, sequence)
            if func.__code__.co_flags & 0x80
            else func(ctx, sequence)
        )
    return ctx
