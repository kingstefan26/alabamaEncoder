from alabamaEncode.adaptive.helpers.bitrateLadder import AutoBitrateLadder


def setup_ssimdb_target(ctx, sequence):
    ab = AutoBitrateLadder(sequence, ctx)

    if (
        not ctx.flag1
        and ctx.prototype_encoder.crf == -1
        and ctx.crf_based_vmaf_targeting is False
        and ctx.vbr_perchunk_optimisation
        and not ctx.find_best_bitrate
    ):
        ctx.ssim_db_target = ab.get_target_ssimdb(ctx.prototype_encoder.bitrate)

    return ctx
