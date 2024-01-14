from alabamaEncode.conent_analysis.chunk.final_encode_steps.dynamic_target_vmaf import (
    DynamicTargetVmaf,
)


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

    # setting up rate control, adaptive or not
    if ctx.weird_x264:
        ctx.chunk_analyze_chain.append(PlainCrf())
    elif ctx.dynamic_vmaf_target:
        print("Using dynamic vmaf targeting")
        ctx.chunk_analyze_chain.append(PlainCrf())
    elif ctx.dynamic_vmaf_target_vbr:
        print("Using dynamic vmaf targeting with vbr")
        ctx.chunk_analyze_chain.append(PlainVbr())
    elif ctx.crf_map != "":
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

    # grain synth, per chunk parameters etc
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

    if ctx.weird_x264:
        from alabamaEncode.conent_analysis.chunk.final_encode_steps.weirdX264 import (
            TargetX264,
        )

        ctx.chunk_encode_class = TargetX264()
        return ctx

    if ctx.flag1:
        ctx.chunk_encode_class = WeridCapedCrfFinalEncode()
    elif ctx.ai_vmaf_targeting:
        ctx.chunk_encode_class = AiTargetedVmafFinalEncode()
    elif ctx.dynamic_vmaf_target:
        ctx.chunk_encode_class = DynamicTargetVmaf()
    elif ctx.dynamic_vmaf_target_vbr:
        from alabamaEncode.conent_analysis.chunk.final_encode_steps.dynamic_target_vmaf_vbr import (
            DynamicTargetVmafVBR,
        )

        ctx.chunk_encode_class = DynamicTargetVmafVBR()
    else:
        ctx.chunk_encode_class = PlainFinalEncode()

    return ctx
