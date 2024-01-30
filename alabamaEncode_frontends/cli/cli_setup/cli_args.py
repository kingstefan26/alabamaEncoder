import argparse

from alabamaEncode.encoder.encoder_enum import EncodersEnum


def read_args(ctx):
    """
    Parse the arguments for the program
    """
    parser = argparse.ArgumentParser(
        description="AlabamaEncoder, one and only encoder framework for all your needs*"
    )
    parser.add_argument("input", type=str, help="Input video file")
    parser.add_argument("output", type=str, help="Output video file")

    parser.add_argument(
        "--encode_audio",
        help="Mux audio",
        action=argparse.BooleanOptionalAction,
        default=ctx.encode_audio,
    )

    parser.add_argument(
        "--audio_params",
        help="Audio params",
        type=str,
        default=ctx.audio_params,
    )

    parser.add_argument(
        "--celery",
        help="Encode on a celery cluster, that is at localhost",
        action="store_true",
        default=ctx.use_celery,
    )

    parser.add_argument(
        "--autocrop",
        help="Automatically crop the video",
        action="store_true",
        default=ctx.auto_crop,
    )

    parser.add_argument(
        "--video_filters",
        type=str,
        default=ctx.prototype_encoder.video_filters,
        help="Override the crop, put your vf ffmpeg there, example "
        "scale=-2:1080:flags=lanczos,zscale=t=linear..."
        " make sure ffmpeg on all workers has support for the filters you use",
    )

    parser.add_argument(
        "--bitrate",
        help="Bitrate to use, `auto` for auto bitrate selection",
        type=str,
        default=str(ctx.prototype_encoder.bitrate),
    )

    parser.add_argument(
        "--overshoot",
        help="How much proc the vbr_perchunk_optimisation is allowed to overshoot",
        type=int,
        default=ctx.bitrate_overshoot,
    )

    parser.add_argument(
        "--undershoot",
        help="How much proc the vbr_perchunk_optimisation is allowed to undershoot",
        type=int,
        default=ctx.bitrate_undershoot,
    )

    parser.add_argument(
        "--vbr_perchunk_optimisation",
        help="Enable automatic bitrate optimisation per chunk",
        action=argparse.BooleanOptionalAction,
        default=ctx.vbr_perchunk_optimisation,
    )

    parser.add_argument(
        "--multiprocess_workers",
        help="Number of workers to use for multiprocessing, if -1 the program will auto scale",
        type=int,
        default=ctx.multiprocess_workers,
    )

    parser.add_argument(
        "--ssim-db-target",
        type=float,
        default=ctx.ssim_db_target,
        help="What ssim dB to target when using auto bitrate,"
        " not recommended to set manually, otherwise 21.2 is a good starting"
        " point",
    )

    parser.add_argument(
        "--crf",
        help="What crf to use",
        type=int,
        default=ctx.prototype_encoder.crf,
        choices=range(0, 63),
    )

    parser.add_argument(
        "--encoder",
        help="What encoder to use",
        type=str,
        default=str(EncodersEnum.SVT_AV1),
        choices=[
            "svt_av1",
            "x265",
            "aomenc",
            "x264",
            "vpx_9",
            "hevc_vaapi",
            "h264_vaapi",
            "rav1e",
        ],
    )

    parser.add_argument(
        "--grain",
        help="Manually give the grainsynth value, 0 to disable, -1 for auto, -2 for auto per scene",
        type=int,
        default=ctx.prototype_encoder.grain_synth,
        choices=range(-2, 63),
    )

    parser.add_argument(
        "--vmaf_target",
        help="What vmaf to target when using bitrate auto",
        default=ctx.vmaf,
        type=int,
    )

    parser.add_argument(
        "--max_scene_length",
        help="If a scene is longer then this, it will recursively cut in the"
        " middle it to get until each chunk is within the max",
        type=int,
        default=ctx.max_scene_length,
        metavar="max_scene_length",
    )

    scene_split_method_group = parser.add_mutually_exclusive_group()

    scene_split_method_group.add_argument(
        "--statically_sized_scenes",
        help="Instead of preforming scene detection do statically sized scenes at about 30secs",
        action="store_true",
        default=ctx.statically_sized_scenes,
    )

    scene_split_method_group.add_argument(
        "--scene_merge",
        help="Merge scenes until they met the max scene length",
        action="store_true",
        default=ctx.scene_merge,
    )

    parser.add_argument(
        "--crf_based_vmaf_targeting",
        help="per chunk, find a crf that hits target quality and encode using that",
        action=argparse.BooleanOptionalAction,
        default=ctx.crf_based_vmaf_targeting,
    )

    parser.add_argument(
        "--auto_crf",
        help="Find a crf that hits target vmaf, calculate a peak bitrate cap, and encode using that",
        action=argparse.BooleanOptionalAction,
        default=ctx.crf_bitrate_mode,
    )

    parser.add_argument(
        "--chunk_order",
        help="Encode chunks in a specific order",
        type=str,
        default=ctx.chunk_order,
        choices=[
            "random",
            "sequential",
            "length_desc",
            "length_asc",
            "sequential_reverse",
        ],
    )

    parser.add_argument(
        "--start_offset",
        help="Offset from the beginning of the video (in seconds), useful for cutting intros etc",
        default=ctx.start_offset,
        type=int,
    )

    parser.add_argument(
        "--end_offset",
        help="Offset from the end of the video (in seconds), useful for cutting end credits outtros etc",
        default=ctx.end_offset,
        type=int,
    )

    parser.add_argument(
        "--bitrate_adjust_mode",
        help="do a complexity analysis on each chunk individually and adjust "
        "bitrate based on that, can overshoot/undershoot a lot, "
        "otherwise do complexity analysis on all chunks ahead of time"
        " and budget it to hit target by normalizing the bitrate",
        type=str,
        default=ctx.bitrate_adjust_mode,
        choices=["chunk", "global"],
    )

    parser.add_argument(
        "--log_level",
        help="Set the log level, 0 silent, 1 verbose",
        type=int,
        default=ctx.log_level,
    )

    parser.add_argument(
        "--generate_previews",
        help="Generate previews for encoded file",
        action=argparse.BooleanOptionalAction,
        default=ctx.generate_previews,
    )

    parser.add_argument(
        "--override_bad_wrong_cache_path",
        help="Override the check for input file path matching in scene cache loading",
        action="store_true",
        default=ctx.override_scenecache_path_check,
    )

    parser.add_argument(
        "--hdr",
        help="Encode in HDR`, if off and input is HDR, it will be tonemapped to SDR",
        action="store_true",
        default=ctx.prototype_encoder.hdr,
    )

    parser.add_argument(
        "--crop_string",
        help="Crop string to use, eg `1920:1080:0:0`, `3840:1600:0:280`. Obtained using the `cropdetect` ffmpeg filter",
        type=str,
        default=ctx.crop_string,
    )

    parser.add_argument(
        "--scale_string",
        help="Scale string to use, eg. `1920:1080`, `1280:-2`, `1920:1080:force_original_aspect_ratio=decrease`",
        type=str,
        default=ctx.scale_string,
    )

    parser.add_argument(
        "--dry_run",
        help="Do not encode, just print what would be done",
        action="store_true",
        default=ctx.dry_run,
    )

    parser.add_argument(
        "--title", help="Title of the video", type=str, default=ctx.title
    )

    parser.add_argument(
        "--encoder_flag_override",
        type=str,
        default=ctx.prototype_encoder.override_flags,
        help="Override the encoder flags with this string, except paths",
    )

    parser.add_argument(
        "--encoder_speed_override",
        type=int,
        choices=range(0, 10),
        default=ctx.prototype_encoder.speed,
        help="Override the encoder speed parameter",
    )

    parser.add_argument(
        "--flag1",
        action="store_true",
        help="find what crf matches config.bitrate, encode at that crf and redo if the crf bitrate is higher then set",
        default=ctx.flag1,
    )

    parser.add_argument(
        "--flag2",
        action="store_true",
        help="Used for debugging",
        default=ctx.flag2,
    )

    parser.add_argument(
        "--flag3",
        action="store_true",
        help="Find best bitrate using the top 5% of most complex chunks",
        default=ctx.flag3,
    )

    parser.add_argument(
        "--flag4",
        type=str,
        help="Map of crf <-> chunk index, for debugging purposes only",
        default=ctx.crf_map,
    )

    parser.add_argument(
        "--color-primaries",
        type=str,
        default=ctx.prototype_encoder.color_primaries,
        help="Color primaries",
    )
    parser.add_argument(
        "--transfer-characteristics",
        type=str,
        default=ctx.prototype_encoder.transfer_characteristics,
        help="Transfer characteristics",
    )
    parser.add_argument(
        "--matrix-coefficients",
        type=str,
        default=ctx.prototype_encoder.matrix_coefficients,
        help="Matrix coefficients",
    )
    parser.add_argument(
        "--maximum_content_light_level",
        type=str,
        default=ctx.prototype_encoder.maximum_content_light_level,
        help="Maximum content light level",
    )

    parser.add_argument(
        "--frame-average-light",
        type=str,
        default=ctx.prototype_encoder.maximum_frame_average_light_level,
        help="Maximum frame average light level",
    )
    parser.add_argument(
        "--chroma-sample-position",
        type=str,
        default=ctx.prototype_encoder.maximum_frame_average_light_level,
        help="Chroma sample position",
    )

    parser.add_argument(
        "--sub_file",
        type=str,
        default=ctx.sub_file,
        help="Subtitles file, eg .srt or .vvt",
    )

    parser.add_argument(
        "--crf_model_weights",
        type=str,
        default=ctx.crf_model_weights,
        help="Weights for the crf model, comma separated, 5 values, see readme",
    )

    parser.add_argument(
        "--vmaf_phone_model",
        action="store_true",
        default=ctx.vmaf_phone_model,
        help="use vmaf phone model for auto crf tuning",
    )

    parser.add_argument(
        "--vmaf_4k_model",
        action="store_true",
        default=ctx.vmaf_4k_model,
        help="use vmaf 4k model for auto crf tuning",
    )

    parser.add_argument(
        "--vmaf_no_motion",
        action="store_true",
        default=ctx.vmaf_no_motion,
        help="use vmaf no motion model for auto crf tuning",
    )

    parser.add_argument(
        "--auto_accept_autocrop",
        action="store_true",
        default=ctx.auto_accept_autocrop,
        help="Automatically accept autocrop",
    )

    parser.add_argument(
        "--resolution_preset",
        type=str,
        default=ctx.resolution_preset,
        help="Preset for the scale filter, possible choices are 4k 1440p 1080p 768p 720p 540p 480p 360p",
    )

    parser.add_argument(
        "--probe_count",
        type=int,
        default=ctx.probe_count,
        help="Max number of probes for metric targeting, higher is more accurate but slower",
    )

    parser.add_argument(
        "--probe_speed_override",
        type=int,
        default=ctx.prototype_encoder.speed,
        help="Override the speed for target vmaf probes",
    )

    parser.add_argument(
        "--vmaf_reference_display",
        type=str,
        default=ctx.vmaf_reference_display,
        choices=["HD", "FHD", "UHD"],
        help="HD FHD UHD",
    )

    parser.add_argument(
        "--vmaf_ai_assisted_targeting",
        action="store_true",
        default=ctx.ai_vmaf_targeting,
        help="use vmaf ai assisted targeting",
    )

    parser.add_argument(
        "--vmaf_target_repesentation",
        type=str,
        default=ctx.vmaf_target_representation,
        help="vmaf target representation, default is mean",
        choices=[
            "mean",
            "min",
            "max",
            "harmonic_mean",
            "percentile_1",
            "percentile_5",
            "percentile_10",
            "percentile_25",
            "percentile_50",
        ],
    )

    parser.add_argument(
        "--simple_denoise",
        action="store_true",
        default=ctx.simple_denoise,
        help="use atadenoise on input, useful for x26 encoding with very noisy imputs and target vmaf, "
        "to be automated in the future",
    )

    parser.add_argument(
        "--dont_pin_to_cores",
        action="store_true",
        default=not ctx.pin_to_cores,
        help="pin each chunk to a core",
    )

    parser.add_argument(
        "--niceness",
        type=int,
        default=ctx.prototype_encoder.niceness,
        help="nice the encoder process",
    )

    parser.add_argument(
        "--weird_x264",
        action="store_true",
        default=ctx.weird_x264,
        help="weird x264 vmaf targeting",
    )

    parser.add_argument(
        "--print_analysis_logs",
        action="store_true",
        help="Print content analysis logs into console, like what crf did vmaf target pick etc",
    )

    parser.add_argument(
        "--poster_url", type=str, help="Url of poster for website updates"
    )

    parser.add_argument(
        "--offload_server",
        type=str,
        default="",
        help="if filled with a server address, will try to send a serialised job to that server",
    )

    parser.add_argument(
        "--dynamic_vmaf_target",
        default=ctx.dynamic_vmaf_target,
        action="store_true",
        help="todo",
    )

    parser.add_argument(
        "--dynamic_vmaf_target_vbr",
        default=ctx.dynamic_vmaf_target_vbr,
        action="store_true",
        help="todo",
    )

    parser.add_argument(
        "--tune",
        default=ctx.args_tune,
        type=str,
        choices=["fidelity", "appeal", "balanced"],
    )

    parser.add_argument(
        "--denoise_vmaf_ref",
        default=ctx.denoise_vmaf_ref,
        action="store_true",
        help="Denoise the vmaf reference",
    )

    parser.add_argument(
        "--dont_calc_final_vmaf",
        default=ctx.dont_calc_final_vmaf,
        action="store_true",
        help="Dont calculate final vmaf",
    )

    parser.add_argument(
        "--multi_res_pipeline",
        default=ctx.multi_res_pipeline,
        action="store_true",
        help="Create a optimised multi tier",
    )

    args = parser.parse_args()

    ctx.output_file = args.output
    ctx.output_folder = ctx.output_file
    ctx.raw_input_file = args.input
    ctx.prototype_encoder = EncodersEnum.from_str(args.encoder).get_encoder()
    ctx.prototype_encoder.grain_synth = args.grain
    ctx.log_level = args.log_level
    ctx.dry_run = args.dry_run
    ctx.ssim_db_target = args.ssim_db_target
    ctx.simple_denoise = args.simple_denoise
    ctx.vmaf = args.vmaf_target
    ctx.vbr_perchunk_optimisation = args.vbr_perchunk_optimisation
    ctx.crf_based_vmaf_targeting = args.crf_based_vmaf_targeting
    ctx.use_celery = args.celery
    ctx.flag1 = args.flag1
    ctx.flag2 = args.flag2
    ctx.flag3 = args.flag3
    ctx.prototype_encoder.override_flags = args.encoder_flag_override
    ctx.prototype_encoder.speed = args.encoder_speed_override
    ctx.multiprocess_workers = args.multiprocess_workers
    ctx.bitrate_adjust_mode = args.bitrate_adjust_mode
    ctx.bitrate_undershoot = args.undershoot
    ctx.bitrate_overshoot = args.overshoot
    ctx.crf_bitrate_mode = args.auto_crf
    ctx.prototype_encoder.crf = args.crf
    ctx.prototype_encoder.hdr = args.hdr
    ctx.max_scene_length = args.max_scene_length
    ctx.start_offset = args.start_offset
    ctx.end_offset = args.end_offset
    ctx.override_scenecache_path_check = args.override_bad_wrong_cache_path
    ctx.crop_string = args.crop_string
    ctx.scale_string = args.scale_string
    ctx.title = args.title
    ctx.chunk_order = args.chunk_order
    ctx.audio_params = args.audio_params
    ctx.generate_previews = ctx.generate_previews
    ctx.encode_audio = args.encode_audio
    ctx.sub_file = args.sub_file
    ctx.prototype_encoder.color_primaries = args.color_primaries
    ctx.prototype_encoder.transfer_characteristics = args.transfer_characteristics
    ctx.prototype_encoder.matrix_coefficients = args.matrix_coefficients
    ctx.prototype_encoder.maximum_content_light_level = args.maximum_content_light_level
    ctx.prototype_encoder.maximum_frame_average_light_level = args.frame_average_light
    ctx.prototype_encoder.chroma_sample_position = args.chroma_sample_position
    ctx.prototype_encoder.video_filters = args.video_filters
    ctx.auto_crop = args.autocrop
    ctx.bitrate_string = args.bitrate
    ctx.crf_model_weights = args.crf_model_weights
    ctx.vmaf_phone_model = args.vmaf_phone_model
    ctx.vmaf_4k_model = args.vmaf_4k_model
    ctx.vmaf_no_motion = args.vmaf_no_motion
    ctx.auto_accept_autocrop = args.auto_accept_autocrop
    ctx.resolution_preset = args.resolution_preset
    ctx.probe_count = args.probe_count
    ctx.vmaf_reference_display = args.vmaf_reference_display
    ctx.probe_speed_override = args.probe_speed_override
    ctx.crf_map = args.flag4
    ctx.ai_vmaf_targeting = args.vmaf_ai_assisted_targeting
    ctx.pin_to_cores = not args.dont_pin_to_cores
    ctx.prototype_encoder.niceness = args.niceness
    ctx.weird_x264 = args.weird_x264
    ctx.vmaf_target_representation = args.vmaf_target_repesentation
    ctx.print_analysis_logs = args.print_analysis_logs
    ctx.poster_url = args.poster_url
    ctx.offload_server = args.offload_server
    ctx.dynamic_vmaf_target = args.dynamic_vmaf_target
    ctx.dynamic_vmaf_target_vbr = args.dynamic_vmaf_target_vbr
    ctx.statically_sized_scenes = args.statically_sized_scenes
    ctx.scene_merge = args.scene_merge
    ctx.args_tune = args.tune
    ctx.denoise_vmaf_ref = args.denoise_vmaf_ref
    ctx.multi_res_pipeline = args.multi_res_pipeline
    ctx.dont_calc_final_vmaf = args.dont_calc_final_vmaf

    return ctx
