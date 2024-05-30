def parse_rd(ctx):
    """
    Sets up the rate distribution mode
    """
    if ctx.bitrate_string is not None and ctx.bitrate_string != "":
        if "auto" in ctx.bitrate_string or "-1" in ctx.bitrate_string:
            ctx.find_best_bitrate = True
        else:
            if "M" in ctx.bitrate_string or "m" in ctx.bitrate_string:
                ctx.bitrate_string = ctx.bitrate_string.replace("M", "")
                ctx.prototype_encoder.bitrate = (
                    int(ctx.prototype_encoder.bitrate) * 1000
                )
            else:
                ctx.bitrate_string = ctx.bitrate_string.replace("k", "")
                ctx.bitrate_string = ctx.bitrate_string.replace("K", "")

                ctx.prototype_encoder.bitrate = int(ctx.bitrate_string)

    return ctx
