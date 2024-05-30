def parse_resolution_presets(ctx):
    """
    Computes the resolution presets
    """
    if ctx.resolution_preset != "" and ctx.scale_string == "":
        # 4k 1440p 1080p 768p 720p 540p 480p 360p
        match ctx.resolution_preset:
            case "4k":
                ctx.scale_string = "3840:-2"
            case "1440p":
                ctx.scale_string = "2560:-2"
            case "1080p":
                ctx.scale_string = "1920:-2"
            case "768p":
                ctx.scale_string = "1366:-2"
            case "720p":
                ctx.scale_string = "1280:-2"
            case "540p":
                ctx.scale_string = "960:-2"
            case "480p":
                ctx.scale_string = "854:-2"
            case "432p":
                ctx.scale_string = "768:-2"
            case "360p":
                ctx.scale_string = "640:-2"
            case "240p":
                ctx.scale_string = "480:-2"
            case _:
                raise ValueError(
                    f'Cannot interpret resolution preset "{ctx.resolution_preset}", refer to the help command'
                )
    return ctx
