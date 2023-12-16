def setup_chunk_analyze_chain(ctx, sequence):
    """
    Sets up the chunk analyze chain
    """
    from alabamaEncode.conent_analysis.chunk.capped_crf import CapedCrf
    from alabamaEncode.conent_analysis.chunk.manual_crf import CrfIndexesMap
    from alabamaEncode.conent_analysis.chunk.optimised_vbr import VbrPerChunkOptimised
    from alabamaEncode.conent_analysis.chunk.per_scene_grain import GrainSynth
    from alabamaEncode.conent_analysis.chunk.plain_crf import PlainCrf
    from alabamaEncode.conent_analysis.chunk.plain_vbr import PlainVbr
    from alabamaEncode.conent_analysis.chunk.target_vmaf import TargetVmaf

    ctx.chunk_analyze_chain = []

    if ctx.crf_map != "":
        ctx.chunk_analyze_chain.append(CrfIndexesMap(ctx.crf_map))
    elif ctx.flag1 is True:
        ctx.chunk_analyze_chain.append(PlainCrf())
    elif ctx.crf_based_vmaf_targeting is True and ctx.ai_vmaf_targeting is False:
        ctx.chunk_analyze_chain.append(
            TargetVmaf(
                alg_type=ctx.vmaf_targeting_model,
                probe_speed=ctx.probe_speed_override,
            )
        )
    else:
        if ctx.crf_bitrate_mode or ctx.ai_vmaf_targeting:
            ctx.chunk_analyze_chain.append(CapedCrf())
        elif ctx.prototype_encoder.crf != -1:
            ctx.chunk_analyze_chain.append(PlainCrf())
        else:
            if ctx.bitrate_adjust_mode == "chunk":
                ctx.chunk_analyze_chain.append(VbrPerChunkOptimised())
            else:
                ctx.chunk_analyze_chain.append(PlainVbr())

    if ctx.prototype_encoder.grain_synth == -2:
        ctx.chunk_analyze_chain.append(GrainSynth())

    if len(ctx.chunk_analyze_chain) == 0:
        raise Exception("Failed to Create the analyze steps in analyzer_factory")

    return ctx


def setup_chunk_encoder(ctx, sequence):
    """
    Sets up the chunk encoder
    """
    from alabamaEncode.conent_analysis.chunk.final_encode_steps.ai_targeted_vmaf import (
        AiTargetedVmafFinalEncode,
    )
    from alabamaEncode.conent_analysis.chunk.final_encode_steps.capped_crf_encode import (
        WeridCapedCrfFinalEncode,
    )
    from alabamaEncode.conent_analysis.chunk.final_encode_steps.plain import (
        PlainFinalEncode,
    )

    if ctx.flag1:
        ctx.chunk_encode_class = WeridCapedCrfFinalEncode()
    elif ctx.ai_vmaf_targeting:
        ctx.chunk_encode_class = AiTargetedVmafFinalEncode()
    else:
        ctx.chunk_encode_class = PlainFinalEncode()

    return ctx
