from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.path import PathAlabama


def parse_video_filters(ctx):
    """
    Sets up the video filters
    """

    vec = ctx.prototype_encoder.video_filters.split(",")

    if ctx.crop_string != "":
        vec.append(f"crop={ctx.crop_string}")

    if ctx.scale_string != "":
        vec.append(f"scale={ctx.scale_string}:flags=lanczos")

    if ctx.prototype_encoder.hdr is False and Ffmpeg.is_hdr(
        PathAlabama(ctx.input_file)
    ):
        print("Input Video is HDR but requested a SDR encode, auto-tonemapping")
        vec.append(Ffmpeg.get_tonemap_vf())

    vec = [string for string in vec if string != ""]

    ctx.prototype_encoder.video_filters = ",".join(vec)
    return ctx
