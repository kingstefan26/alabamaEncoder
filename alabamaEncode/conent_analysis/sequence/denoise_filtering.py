def setup_denoise(ctx, sequence):
    """
    Sets up a denoise filter
    """
    if ctx.simple_denoise:
        print("Using simple denoise")
        vf = ctx.prototype_encoder.video_filters.split(",")
        vf.append("atadenoise")
        ctx.prototype_encoder.video_filters = ",".join(vf)

    return ctx
