from alabamaEncode.adaptive.helpers.bitrateLadder import AutoBitrateLadder


def setup_ideal_bitrate(ctx, sequence):
    ab = AutoBitrateLadder(sequence, ctx)

    if (
        not ctx.flag1
        and ctx.prototype_encoder.crf == -1
        and ctx.crf_based_vmaf_targeting is False
        and ctx.find_best_bitrate
        and not ctx.vbr_perchunk_optimisation
    ):
        ctx.prototype_encoder.bitrate = ab.get_best_bitrate()

    return ctx
