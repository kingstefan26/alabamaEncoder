from alabamaEncode.adaptive.helpers.bitrateLadder import AutoBitrateLadder


def setup_ideal_crf_weighted(ctx, sequence):
    ab = AutoBitrateLadder(sequence, ctx)

    if ctx.flag1:
        ab.get_best_crf_guided()
    return ctx
