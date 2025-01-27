def setup_chunk_analyze_chain(ctx):
    """
    Sets up the chunk analyze chain
    """
    from alabamaEncode.pipeline.chunk.analyze_steps.manual_crf import (
        CrfIndexesMap,
    )
    from alabamaEncode.pipeline.chunk.analyze_steps.optimised_vbr import (
        VbrPerChunkOptimised,
    )
    from alabamaEncode.pipeline.chunk.analyze_steps.per_scene_grain import (
        GrainSynth,
    )
    from alabamaEncode.pipeline.chunk.analyze_steps.new_grain import (
        NewGrainSynth,
    )
    from alabamaEncode.pipeline.chunk.analyze_steps.plain_crf import PlainCrf
    from alabamaEncode.pipeline.chunk.analyze_steps.plain_vbr import PlainVbr
    from alabamaEncode.pipeline.chunk.analyze_steps.target_vmaf import TargetVmaf
    from alabamaEncode.pipeline.chunk.analyze_steps.multires_encode_candidates import (
        EncodeMultiResCandidates,
    )

    ctx.chunk_analyze_chain = []

    # grain synth, per chunk parameters etc.
    if ctx.prototype_encoder.grain_synth == -2:
        ctx.chunk_analyze_chain.append(GrainSynth())
    elif ctx.prototype_encoder.grain_synth == -3:
        ctx.chunk_analyze_chain.append(NewGrainSynth())

    # setting up rate control, adaptive or not
    if ctx.bitrate_adjust_mode == "chunk":
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
    elif ctx.crf_based_vmaf_targeting is True and ctx.multi_res_pipeline is False:
        ctx.chunk_analyze_chain.append(TargetVmaf())
    elif ctx.prototype_encoder.crf != -1:
        ctx.chunk_analyze_chain.append(PlainCrf())
    else:
        ctx.chunk_analyze_chain.append(PlainVbr())

    # luma boost is done after initial rate control, since its ment as an addition
    if ctx.luma_boost is True:
        from alabamaEncode.pipeline.chunk.analyze_steps.luma_boost import (
            LumaBoost,
        )

        ctx.chunk_analyze_chain.append(LumaBoost())

    if len(ctx.chunk_analyze_chain) == 0:
        raise Exception("Failed to Create the analyze steps in analyzer_factory")

    return ctx
