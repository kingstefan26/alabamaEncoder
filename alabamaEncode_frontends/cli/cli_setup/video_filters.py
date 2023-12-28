from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama


def parse_video_filters(ctx):
    """
    Sets up the video filters
    """
    # make --video_filters mutually exclusive with --hdr --crop_string --scale_string
    # if ctx.prototype_encoder.video_filters != "" and (
    #     ctx.prototype_encoder.hdr
    #     or ctx.prototype_encoder.video_filters != ""
    #     or ctx.scale_string != ""
    # ):
    #     print(
    #         "--video_filters is mutually exclusive with --hdr, --crop_string, and --scale_string"
    #     )
    #     quit()

    if ctx.prototype_encoder.video_filters == "":
        final = ""

        if ctx.crop_string != "":
            final += f"crop={ctx.crop_string}"

        if ctx.scale_string != "":
            if final != "" and final[-1] != ",":
                final += ","
            final += f"scale={ctx.scale_string}:flags=lanczos"

        if ctx.prototype_encoder.hdr is False and Ffmpeg.is_hdr(
            PathAlabama(ctx.input_file)
        ):
            if final != "" and final[-1] != ",":
                final += ","
            final += Ffmpeg.get_tonemap_vf()

        ctx.prototype_encoder.video_filters = final
    return ctx
