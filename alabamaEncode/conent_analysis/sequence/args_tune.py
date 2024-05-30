from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.scene.sequence import ChunkSequence


def tune_args_for_fdlty_or_apl(ctx: AlabamaContext, sequence: ChunkSequence):
    match ctx.args_tune:
        case "fidelity":
            ctx.log("Tuning for fidelity", category="analyzing_content_logs")
            if ctx.simple_denoise:
                for _ in range(3):
                    ctx.log(
                        "YOU ARE USING SIMPLE DENOISE, THIS IS NOT RECOMMENDED FOR FIDELITY TUNING",
                        category="analyzing_content_logs"
                    )
            ctx.prototype_encoder.svt_tune = 1
            ctx.prototype_encoder.svt_tf = 0
            ctx.prototype_encoder.svt_enable_variance_boost = 1

        case "appeal":
            ctx.log("Tuning for appeal", category="analyzing_content_logs")
            ctx.prototype_encoder.qm_max = 8
            ctx.prototype_encoder.qm_min = 0
            ctx.prototype_encoder.svt_tune = 0
            ctx.prototype_encoder.svt_enable_variance_boost = 0
        case "balanced":
            ctx.log("Tuning for balanced appeal and fidelity")
            ctx.prototype_encoder.svt_tune = 0
        case _:
            raise RuntimeError(f"Invalid args_tune: {ctx.args_tune}")

    if isinstance(ctx.prototype_encoder, EncoderSvt) and ctx.prototype_encoder.is_psy():
        ctx.log("Found svt psy, using tune 3", category="analyzing_content_logs")
        ctx.prototype_encoder.svt_tune = 3

    return ctx
