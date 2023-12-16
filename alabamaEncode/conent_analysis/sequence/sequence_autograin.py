from alabamaEncode.adaptive.helpers.grain import get_best_avg_grainsynth


def setup_autograin(ctx, sequence):
    if (
        ctx.prototype_encoder.grain_synth == -1
        and ctx.prototype_encoder.supports_grain_synth()
    ):
        param = {
            "input_file": sequence.input_file,
            "scenes": sequence,
            "temp_folder": ctx.temp_folder,
            "cache_filename": ctx.temp_folder + "/adapt/ideal_grain.pt",
            "scene_pick_seed": 2,
            "video_filters": ctx.prototype_encoder.video_filters,
        }
        if ctx.crf_bitrate_mode:
            param["crf"] = ctx.prototype_encoder.crf
        else:
            param["bitrate"] = ctx.prototype_encoder.bitrate

        ctx.prototype_encoder.grain_synth = get_best_avg_grainsynth(**param)

    return ctx
