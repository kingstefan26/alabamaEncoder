from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.scene.sequence import ChunkSequence


def setup_denoise(ctx: AlabamaContext, sequence: ChunkSequence):
    """
    Sets up a denoise filter
    """
    if ctx.simple_denoise:
        print("Using simple denoise")

        # ctx.prototype_encoder.film_grain_denoise = 1
        vf = ctx.prototype_encoder.video_filters.split(",")
        vf = [_x for _x in vf if _x != ""]
        vf.append("atadenoise")
        ctx.prototype_encoder.video_filters = ",".join(vf)

    return ctx
