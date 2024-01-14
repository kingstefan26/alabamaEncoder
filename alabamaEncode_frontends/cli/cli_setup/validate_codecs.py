from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama


def validate_codecs(ctx):
    codec = Ffmpeg.get_codec(PathAlabama(ctx.input_file))
    if codec == "vc1":
        print("Input file is VC1, VC1 ffmpeg seeking is broken, please create a proxy")
        quit()

    return ctx
