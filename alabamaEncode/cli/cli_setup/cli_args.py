import argparse

from argparse_range import range_action

from alabamaEncode.encoder.encoder_factory import (
    get_all_encoder_strings,
    get_encoder_from_string,
)
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt


def read_args(ctx):
    """
    Parse the arguments for the program
    """
    parser = argparse.ArgumentParser(
        prog="AlabamaEncoder",
        description="AlabamaEncoder, one and only encoder framework for all your needs*",
        epilog="*not really",
    )

    subparsers = parser.add_subparsers(dest="command")

    worker_parser = subparsers.add_parser("worker", help="Celery worker mode")
    worker_parser.add_argument(
        "--workers",
        "-workers",
        type=int,
        help="Amount of multiprocess workers",
        default=2,
        dest="workers",
    )

    subparsers.add_parser("clear", help="clear celery queue")

    auto_thumbnailer = subparsers.add_parser(
        "autothumbnailer", help="Pick and extract perfect thumbnail frames"
    )

    auto_thumbnailer.add_argument("input", type=str, help="Input video file")

    auto_thumbnailer.add_argument(
        "--detect_faces",
        action="store_true",
        help="Detect faces in video",
        dest="detect_faces",
    )

    encode = subparsers.add_parser("encode", help="Typical encode mode")

    encode.add_argument("input", type=str, help="Input video file")
    encode.add_argument("output", type=str, help="Output video file")

    encode.add_argument(
        "--dont_encode_audio",
        help="Mux audio",
        action="store_false",
        dest="encode_audio",
    )

    encode.add_argument(
        "--audio_params",
        help="Audio params",
        type=str,
        default=ctx.audio_params,
        dest="audio_params",
    )

    encode.add_argument(
        "--celery",
        help="Encode on a celery cluster, that is at localhost",
        action="store_true",
        default=ctx.use_celery,
        dest="use_celery",
    )

    encode.add_argument(
        "--autocrop",
        help="Automatically crop the video",
        action="store_true",
        default=ctx.auto_crop,
        dest="auto_crop",
    )

    encode.add_argument(
        "--video_filters",
        type=str,
        default=ctx.prototype_encoder.video_filters,
        help="Override the crop, put your vf ffmpeg there, example "
        "scale=-2:1080:flags=lanczos,zscale=t=linear..."
        " make sure ffmpeg on all workers has support for the filters you use",
    )

    encode.add_argument(
        "--bitrate",
        help="Bitrate to use, `auto` for auto bitrate selection",
        type=str,
        default=str(ctx.prototype_encoder.bitrate),
    )

    encode.add_argument(
        "--overshoot",
        help="How much proc the vbr_perchunk_optimisation is allowed to overshoot",
        type=int,
        default=ctx.bitrate_overshoot,
        dest="bitrate_overshoot",
    )

    encode.add_argument(
        "--undershoot",
        help="How much proc the vbr_perchunk_optimisation is allowed to undershoot",
        type=int,
        default=ctx.bitrate_undershoot,
        dest="bitrate_undershoot",
    )

    encode.add_argument(
        "--vbr_perchunk_optimisation",
        help="Enable automatic bitrate optimisation per chunk",
        action="store_true",
        dest="vbr_perchunk_optimisation",
    )

    encode.add_argument(
        "--multiprocess_workers",
        "--workers",
        "-j",
        help="Number of workers to use for multiprocessing, if -1 the program will auto scale",
        type=int,
        default=ctx.multiprocess_workers,
        dest="multiprocess_workers",
    )

    encode.add_argument(
        "--ssim-db-target",
        type=float,
        default=ctx.ssim_db_target,
        help="What ssim dB to target when using auto bitrate, not recommended to set manually, "
        "otherwise 21.2 is a good starting point",
        dest="ssim_db_target",
    )

    encode.add_argument(
        "--crf",
        help="What crf to use",
        type=int,
        default=ctx.prototype_encoder.crf,
        action=range_action(0, 255),
        dest="crf",
    )

    encode.add_argument(
        "--encoder",
        help="What encoder to use",
        type=str,
        default=EncoderSvt().get_pretty_name(),
        choices=get_all_encoder_strings(),
        dest="encoder",
    )

    encode.add_argument(
        "--grain",
        help="Manually give the grainsynth value, 0 to disable, -1 for auto, -2 for auto per scene, -3 for new fast "
        "per scene grain",
        type=int,
        default=ctx.prototype_encoder.grain_synth,
        dest="grain",
    )

    encode.add_argument(
        "--vmaf_target",
        help="What vmaf to target when using bitrate auto",
        default=ctx.vmaf,
        type=int,
        dest="vmaf_target",
    )

    encode.add_argument(
        "--max_scene_length",
        help="If a scene is longer then this, it will recursively cut in the"
        " middle it to get until each chunk is within the max",
        type=int,
        default=ctx.max_scene_length,
        dest="max_scene_length",
    )

    scene_split_method_group = encode.add_mutually_exclusive_group()

    scene_split_method_group.add_argument(
        "--statically_sized_scenes",
        help="Instead of preforming scene detection do statically sized scenes at about 30secs",
        action="store_true",
        dest="statically_sized_scenes",
    )

    scene_split_method_group.add_argument(
        "--scene_merge",
        help="Merge scenes until they met the max scene length",
        action="store_true",
        dest="scene_merge",
    )

    encode.add_argument(
        "--no_crf_based_vmaf_targeting",
        "--crf_mode",
        help="per chunk, find a crf that hits target quality and encode using that",
        action="store_false",
        dest="crf_based_vmaf_targeting",
    )

    encode.add_argument(
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
            "even",
        ],
        dest="chunk_order",
    )

    encode.add_argument(
        "--start_offset",
        help="Offset from the beginning of the video (in seconds), useful for cutting intros etc",
        default=ctx.start_offset,
        type=int,
        dest="start_offset",
    )

    encode.add_argument(
        "--end_offset",
        help="Offset from the end of the video (in seconds), useful for cutting end credits outtros etc",
        default=ctx.end_offset,
        type=int,
        dest="end_offset",
    )

    encode.add_argument(
        "--bitrate_adjust_mode",
        help="do a complexity analysis on each chunk individually and adjust "
        "bitrate based on that, can overshoot/undershoot a lot, "
        "otherwise do complexity analysis on all chunks ahead of time"
        " and budget it to hit target by normalizing the bitrate",
        type=str,
        default=ctx.bitrate_adjust_mode,
        choices=["chunk", "global"],
        dest="bitrate_adjust_mode",
    )

    encode.add_argument(
        "--log_level",
        help="Set the log level, 0 silent, 1 verbose",
        type=int,
        default=ctx.log_level,
        dest="log_level",
    )

    encode.add_argument(
        "--generate_previews",
        "-previews",
        help="Dont generate previews for encoded file",
        action="store_true",
        dest="generate_previews",
    )

    encode.add_argument(
        "--generate_stats",
        "-stats",
        help="Generate stats for encoded file",
        action="store_true",
        dest="generate_stats",
    )

    encode.add_argument(
        "--override_bad_wrong_cache_path",
        help="Override the check for input file path matching in scene cache loading",
        action="store_true",
        default=ctx.override_scenecache_path_check,
        dest="override_bad_wrong_cache_path",
    )

    encode.add_argument(
        "--hdr",
        "-hdr",
        help="Encode in HDR, if not specified and input is hdr it will automatically tonemap",
        action="store_true",
        default=ctx.prototype_encoder.hdr,
        dest="hdr",
    )

    encode.add_argument(
        "--crop_string",
        help="Crop string to use, eg `1920:1080:0:0`, `3840:1600:0:280`. Obtained using the `cropdetect` ffmpeg filter",
        type=str,
        default=ctx.crop_string,
        dest="crop_string",
    )

    encode.add_argument(
        "--scale_string",
        help="Scale string to use, eg. `1920:1080`, `1280:-2`, `1920:1080:force_original_aspect_ratio=decrease`",
        type=str,
        default=ctx.scale_string,
        dest="scale_string",
    )

    encode.add_argument(
        "--dry_run",
        help="Do not encode, just print what would be done",
        action="store_true",
        dest="dry_run",
    )

    encode.add_argument(
        "--title", help="Title of the video", type=str, default=ctx.title, dest="title"
    )

    encode.add_argument(
        "--encoder_flag_override",
        type=str,
        default=ctx.prototype_encoder.override_flags,
        help="Override the encoder flags with this string, write all params except paths",
        dest="encoder_flag_override",
    )

    encode.add_argument(
        "--encoder_speed_override",
        "--enc_speed",
        type=int,
        action=range_action(0, 10),
        default=ctx.prototype_encoder.speed,
        help="Override the encoder speed parameter",
        dest="encoder_speed_override",
    )

    encode.add_argument(
        "--crf_map",
        type=str,
        help="Map of crf <-> chunk index, for debugging purposes only",
        default=ctx.crf_map,
        dest="crf_map",
    )

    encode.add_argument(
        "--color-primaries",
        type=str,
        default=ctx.prototype_encoder.color_primaries,
        help="Color primaries",
        dest="color_primaries",
    )
    encode.add_argument(
        "--transfer-characteristics",
        type=str,
        default=ctx.prototype_encoder.transfer_characteristics,
        help="Transfer characteristics",
        dest="transfer_characteristics",
    )
    encode.add_argument(
        "--matrix-coefficients",
        type=str,
        default=ctx.prototype_encoder.matrix_coefficients,
        help="Matrix coefficients",
        dest="matrix_coefficients",
    )
    encode.add_argument(
        "--maximum_content_light_level",
        type=str,
        default=ctx.prototype_encoder.maximum_content_light_level,
        help="Maximum content light level",
        dest="maximum_content_light_level",
    )

    encode.add_argument(
        "--frame-average-light",
        type=str,
        default=ctx.prototype_encoder.maximum_frame_average_light_level,
        help="Maximum frame average light level",
        dest="frame_average_light",
    )
    encode.add_argument(
        "--chroma-sample-position",
        type=str,
        default=ctx.prototype_encoder.chroma_sample_position,
        help="Chroma sample position",
    )

    encode.add_argument(
        "--sub_file",
        type=str,
        default=ctx.sub_file,
        help="Subtitles file, eg .srt or .vvt",
        dest="sub_file",
    )

    encode.add_argument(
        "--crf_limits",
        type=str,
        help="limits for crf when targeting vmaf, comma separated eg 20,35",
        dest="crf_limits",
    )

    encode.add_argument(
        "--vmaf_phone_model",
        action="store_true",
        help="use vmaf phone model for auto crf tuning",
        default=ctx.vmaf_phone_model,
    )

    encode.add_argument(
        "--vmaf_4k_model",
        action="store_true",
        help="use vmaf 4k model for auto crf tuning",
        dest="vmaf_4k_model",
    )

    encode.add_argument(
        "--vmaf_subsample",
        type=int,
        help="compute scores only every N frames",
        dest="vmaf_subsample",
    )

    encode.add_argument(
        "--vmaf_no_motion",
        action="store_true",
        help="use vmaf no motion model for auto crf tuning",
        dest="vmaf_no_motion",
    )

    encode.add_argument(
        "--auto_accept_autocrop",
        action="store_true",
        help="Automatically accept autocrop",
        dest="auto_accept_autocrop",
    )

    encode.add_argument(
        "--resolution_preset",
        "-res",
        type=str,
        default=ctx.resolution_preset,
        help="Preset for the scale filter, possible choices are 4k 1440p 1080p 768p 720p 540p 480p 360p",
        dest="resolution_preset",
    )

    encode.add_argument(
        "--probe_count",
        type=int,
        default=ctx.probe_count,
        help="Max number of probes for metric targeting, higher is more accurate but slower",
        action=range_action(1, 10),
        dest="probe_count",
    )

    encode.add_argument(
        "--vmaf_probe_speed",
        dest="vmaf_probe_speed",
        type=int,
        default=ctx.vmaf_probe_speed,
        help="Override the speed for target vmaf probes",
        action=range_action(0, 10),
    )

    encode.add_argument(
        "--vmaf_reference_display",
        type=str,
        default=ctx.vmaf_reference_display,
        choices=["HD", "FHD", "UHD"],
        help="HD FHD UHD",
        dest="vmaf_reference_display",
    )

    encode.add_argument(
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
        dest="vmaf_target_repesentation",
    )

    encode.add_argument(
        "--simple_denoise",
        action="store_true",
        help="use atadenoise on input, useful for x26 encoding with very noisy imputs and target vmaf, "
        "to be automated in the future",
        dest="simple_denoise",
    )

    encode.add_argument(
        "--dont_pin_to_cores",
        action="store_false",
        help="pin each chunk to a core",
        dest="dont_pin_to_cores",
    )

    encode.add_argument(
        "--niceness",
        type=int,
        default=ctx.prototype_encoder.niceness,
        help="nice the encoder process",
        dest="niceness",
    )

    encode.add_argument(
        "--print_analysis_logs",
        action="store_true",
        help="Print content analysis logs into console, like what crf did vmaf target pick etc",
        dest="print_analysis_logs",
    )

    encode.add_argument(
        "--poster_url",
        type=str,
        help="Url of poster for website updates",
        dest="poster_url",
    )

    encode.add_argument(
        "--offload_server",
        type=str,
        default="",
        help="if filled with a server address, will try to send a serialised job to that server",
        dest="offload_server",
    )

    encode.add_argument(
        "--metric_to_target",
        default=ctx.metric_to_target,
        choices=["vmaf", "ssimu2"],
        help="Uses all the vmaf target logic but a different metric",
        dest="metric_to_target",
    )

    encode.add_argument(
        "--dynamic_vmaf_target",
        action="store_true",
        help="Target vmaf and weight it against the bitrate, useful for lossy sources that trick vmaf into low scores",
        dest="dynamic_vmaf_target",
    )

    encode.add_argument(
        "--dynamic_vmaf_target_vbr",
        action="store_true",
        help="vmaf targeting but instead of tuning crf, we tune the bitrate and use variable bitrate encoding",
        dest="dynamic_vmaf_target_vbr",
    )

    encode.add_argument(
        "--tune",
        default=ctx.args_tune,
        type=str,
        choices=["fidelity", "appeal", "balanced"],
        help="Tune the encoder setting for a specific use case",
        dest="tune",
    )

    encode.add_argument(
        "--denoise_vmaf_ref",
        action="store_true",
        help="Denoise the vmaf reference",
        dest="denoise_vmaf_ref",
    )

    encode.add_argument(
        "--calc_final_vmaf",
        default=ctx.calc_final_vmaf,
        action="store_true",
        help="Calculate vmaf of the final chunk at the end",
        dest="calc_final_vmaf",
    )

    encode.add_argument(
        "--multi_res_pipeline",
        action="store_true",
        help="Create a optimised multi bitrate tier stream",
        dest="multi_res_pipeline",
    )

    encode.add_argument(
        "--throughput_scaling",
        action="store_true",
        help="Scale the multi-process workers based on throughput",
        dest="throughput_scaling",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        quit()

    if (
        args.command == "autothumbnailer"
        or args.command == "worker"
        or args.command == "clear"
    ):
        return ctx, args

    ctx.output_file = args.output
    ctx.output_folder = ctx.output_file
    ctx.raw_input_file = args.input
    ctx.prototype_encoder = get_encoder_from_string(args.encoder)
    ctx.prototype_encoder.grain_synth = args.grain
    ctx.log_level = args.log_level
    ctx.dry_run = args.dry_run
    ctx.ssim_db_target = args.ssim_db_target
    ctx.simple_denoise = args.simple_denoise
    ctx.vmaf = args.vmaf_target
    ctx.vbr_perchunk_optimisation = args.vbr_perchunk_optimisation
    ctx.crf_based_vmaf_targeting = args.crf_based_vmaf_targeting
    ctx.use_celery = args.use_celery
    ctx.prototype_encoder.override_flags = args.encoder_flag_override
    ctx.prototype_encoder.speed = args.encoder_speed_override
    ctx.multiprocess_workers = args.multiprocess_workers
    ctx.bitrate_adjust_mode = args.bitrate_adjust_mode
    ctx.bitrate_undershoot = args.bitrate_undershoot
    ctx.bitrate_overshoot = args.bitrate_overshoot
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
    ctx.generate_previews = args.generate_previews
    ctx.generate_stats = args.generate_stats
    ctx.encode_audio = args.encode_audio
    ctx.sub_file = args.sub_file
    ctx.prototype_encoder.color_primaries = args.color_primaries
    ctx.prototype_encoder.transfer_characteristics = args.transfer_characteristics
    ctx.prototype_encoder.matrix_coefficients = args.matrix_coefficients
    ctx.prototype_encoder.maximum_content_light_level = args.maximum_content_light_level
    ctx.prototype_encoder.maximum_frame_average_light_level = args.frame_average_light
    ctx.prototype_encoder.chroma_sample_position = args.chroma_sample_position
    ctx.prototype_encoder.video_filters = args.video_filters
    ctx.auto_crop = args.auto_crop
    ctx.bitrate_string = args.bitrate
    ctx.crf_limits = args.crf_limits
    ctx.vmaf_phone_model = args.vmaf_phone_model
    ctx.vmaf_4k_model = args.vmaf_4k_model
    ctx.vmaf_subsample = args.vmaf_subsample
    ctx.vmaf_no_motion = args.vmaf_no_motion
    ctx.auto_accept_autocrop = args.auto_accept_autocrop
    ctx.resolution_preset = args.resolution_preset
    ctx.probe_count = args.probe_count
    ctx.vmaf_reference_display = args.vmaf_reference_display
    ctx.vmaf_probe_speed = args.vmaf_probe_speed
    ctx.crf_map = args.crf_map
    ctx.pin_to_cores = args.dont_pin_to_cores
    ctx.prototype_encoder.niceness = args.niceness
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
    ctx.calc_final_vmaf = args.calc_final_vmaf
    ctx.metric_to_target = args.metric_to_target
    ctx.throughput_scaling = args.throughput_scaling

    return ctx, args
