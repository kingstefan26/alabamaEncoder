from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.scene.sequence import ChunkSequence


def tune_args_for_fdlty_or_apl(ctx: AlabamaContext, sequence: ChunkSequence):
    match ctx.args_tune:
        case "fidelity":
            print("Tuning for fidelity")
            if ctx.simple_denoise:
                for _ in range(3):
                    print(
                        "YOU ARE USING SIMPLE DENOISE, THIS IS NOT RECOMMENDED FOR FIDELITY TUNING"
                    )
            ctx.prototype_encoder.qm_enabled = 0
            ctx.prototype_encoder.svt_tune = 2
            ctx.prototype_encoder.svt_tf = 0
        case "appeal":
            print("Tuning for appeal")
            ctx.prototype_encoder.qm_enabled = 1
            ctx.prototype_encoder.qm_max = 8
            ctx.prototype_encoder.qm_min = 0
            ctx.prototype_encoder.svt_tune = 0
        case "balanced":
            print("Tuning for balanced appeal and fidelity")
            ctx.prototype_encoder.qm_enabled = 1
            ctx.prototype_encoder.qm_max = 15
            ctx.prototype_encoder.qm_min = 8
            ctx.prototype_encoder.svt_tune = 0
        case _:
            raise RuntimeError(f"Invalid args_tune: {ctx.args_tune}")

    if isinstance(ctx.prototype_encoder, EncoderSvt) and ctx.prototype_encoder.is_psy():
        print("Found svt psy, using tune 3")
        ctx.prototype_encoder.svt_tune = 3

    return ctx
