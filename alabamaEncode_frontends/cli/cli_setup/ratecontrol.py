def parse_rd(ctx):
    """
    Sets up the rate distribution mode
    """
    if ctx.prototype_encoder.crf == -1:
        if "auto" in ctx.bitrate_string or "-1" in ctx.bitrate_string:
            if ctx.flag1 and not ctx.crf_based_vmaf_targeting:
                print("Flag1 and auto bitrate are mutually exclusive")
                quit()
            ctx.find_best_bitrate = True
        else:
            if "M" in ctx.bitrate_string or "m" in ctx.bitrate_string:
                ctx.prototype_encoder.bitrate = ctx.bitrate_string.replace("M", "")
                ctx.prototype_encoder.bitrate = (
                    int(ctx.prototype_encoder.bitrate) * 1000
                )
            else:
                ctx.prototype_encoder.bitrate = ctx.bitrate_string.replace("k", "")
                ctx.prototype_encoder.bitrate = ctx.bitrate_string.replace("K", "")

                try:
                    ctx.prototype_encoder.bitrate = int(ctx.bitrate_string)
                except ValueError:
                    raise ValueError("Failed to parse bitrate")

        if ctx.flag1 and ctx.prototype_encoder.bitrate == -1:
            print("Flag1 requires bitrate to be set --bitrate 2M")
            quit()
    return ctx
