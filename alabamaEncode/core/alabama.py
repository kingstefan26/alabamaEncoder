import argparse
import json
import os
import time
from typing import List

from tqdm import tqdm

from alabamaEncode.adaptive.sub.crop_detect import do_cropdetect
from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.encoder_enum import EncodersEnum
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution


class AlabamaContext:
    """A class to hold the configuration for an encoding instance"""

    def __str__(self):
        return self.__dict__.__str__()

    video_filters: str = ""
    bitrate: int = 2000
    temp_folder: str = ""
    output_folder: str = ""
    output_file: str = ""
    input_file: str = ""
    raw_input_file: str = ""
    vbr_perchunk_optimisation: bool = True
    vmaf: int = 96
    ssim_db_target: float = 20
    grain_synth: int = 0
    passes: (1 or 2 or 3) = 3
    crf: float = -1
    speed: int = 4
    rate_distribution: EncoderRateDistribution = EncoderRateDistribution.CQ
    threads: int = 1
    qm_enabled: bool = False
    qm_min: int = 8
    qm_max: int = 15
    film_grain_denoise: (0 | 1) = 1
    crf_bitrate_mode: bool = False
    max_bitrate: int = 0
    encoder: EncodersEnum = None
    bitrate_undershoot: float = 0.90
    bitrate_overshoot: float = 2
    bitrate_adjust_mode: str = "chunk"
    use_celery: bool = False
    multiprocess_workers: int = -1
    log_level: int = 0
    dry_run: bool = False
    flag1: bool = False
    flag2: bool = False
    flag3: bool = False
    cutoff_bitrate: int = -1
    override_flags: str = ""
    bitrate_string = ""
    crf_model_weights = "7,2,10,2,7"
    vmaf_targeting_model = "binary"
    vmaf_probe_count = 5
    vmaf_reference_display = ""

    resolution_preset = ""

    chunk_stats_path: str = ""
    find_best_bitrate = False
    find_best_grainsynth = False
    crop_string = ""
    scale_string = ""

    crf_based_vmaf_targeting = True
    vmaf_4k_model = False
    vmaf_phone_model = False

    max_scene_length: int = 10
    start_offset: int = -1
    end_offset: int = -1
    override_scenecache_path_check: bool = False
    title = ""
    sub_file = ""
    chunk_order = "sequential"
    audio_params = (
        "-c:a libopus -ac 2 -b:v 96k -vbr on -lfe_mix_level 0.5 -mapping_family 1"
    )
    generate_previews = True
    encoder_name = "SouAV1R"
    encode_audio = True
    auto_crop = False
    auto_accept_autocrop = False
    probe_speed_override = speed

    hdr = False
    color_primaries = "bt709"
    transfer_characteristics = "bt709"
    matrix_coefficients = "bt709"
    maximum_content_light_level: int = 0
    maximum_frame_average_light_level: int = 0
    chroma_sample_position = 0
    svt_master_display = ""

    def log(self, msg, level=0):
        if self.log_level > 0 and level <= self.log_level:
            tqdm.write(msg)

    def get_encoder(self) -> Encoder:
        return self.encoder.get_encoder()


def setup_video_filters(ctx: AlabamaContext) -> AlabamaContext:
    # make --video_filters mutually exclusive with --hdr --crop_string --scale_string
    if ctx.video_filters != "" and (
        ctx.hdr or ctx.video_filters != "" or ctx.scale_string != ""
    ):
        print(
            "--video_filters is mutually exclusive with --hdr, --crop_string, and --scale_string"
        )
        quit()

    if ctx.video_filters == "":
        final = ""

        if ctx.crop_string != "":
            final += f"crop={ctx.crop_string}"

        if ctx.scale_string != "":
            if final != "" and final[-1] != ",":
                final += ","
            final += f"scale={ctx.scale_string}:flags=lanczos"

        if ctx.hdr is False and Ffmpeg.is_hdr(PathAlabama(ctx.input_file)):
            if final != "" and final[-1] != ",":
                final += ","
            final += Ffmpeg.get_tonemap_vf()

        ctx.video_filters = final
    return ctx


def setup_paths(ctx: AlabamaContext) -> AlabamaContext:
    # turn tempfolder into a full path
    ctx.output_folder = os.path.normpath(ctx.output_folder)

    ctx.temp_folder = os.path.join(ctx.output_folder, "temp")
    if not os.path.exists(ctx.temp_folder):
        os.makedirs(ctx.temp_folder)

    ctx.temp_folder += "/"

    ctx.input_file = os.path.join(ctx.temp_folder, "temp.mkv")

    if not os.path.exists(ctx.raw_input_file):
        print(f"Input file {ctx.raw_input_file} does not exist")
        quit()

    # symlink input file to temp folder
    if not os.path.exists(ctx.input_file):
        os.symlink(ctx.raw_input_file, ctx.input_file)
        # if os.name == 'nt':
        #     os
        #     run_cli(f'New-Item -ItemType SymbolicLink -Path "{ctx.raw_input_file}" -Target "{ctx.input_file}"')
        # else:
        #     os.system(f'ln -s "{ctx.raw_input_file}" "{ctx.input_file}"')
        if not os.path.exists(ctx.input_file):
            print(f"Failed to symlink input file to {ctx.input_file}")
            quit()

    return ctx


def scrape_hdr_metadata(ctx: AlabamaContext) -> AlabamaContext:
    if ctx.hdr and (
        ctx.encoder == EncodersEnum.SVT_AV1 or ctx.encoder == EncodersEnum.X264
    ):
        if not Ffmpeg.is_hdr(PathAlabama(ctx.raw_input_file)):
            print("Input file is not HDR, disabling HDR mode")
            ctx.hdr = False
            return ctx

        cache_path = f"{ctx.temp_folder}hdr.cache"
        if not os.path.exists(cache_path):
            print("Running auto HDR10")
            obj = Ffmpeg.get_first_frame_data(PathAlabama(ctx.raw_input_file))
            color_space = obj["color_space"]
            if "bt2020nc" in color_space:
                color_space = "bt2020-ncl"

            if ctx.matrix_coefficients == "bt709":
                ctx.matrix_coefficients = color_space
                print(f"Setting color space to {ctx.matrix_coefficients}")

            if ctx.color_primaries == "bt709":
                ctx.color_primaries = obj["color_primaries"]
                print(f"Setting color primaries to {ctx.color_primaries}")

            if ctx.transfer_characteristics == "bt709":
                ctx.transfer_characteristics = obj["color_transfer"]
                print(
                    f"Setting transfer characteristics to {ctx.transfer_characteristics}"
                )

            ctx.chroma_sample_position = obj["chroma_location"]
            print(f"Setting chroma sample position to {ctx.chroma_sample_position}")

            for side_data in obj["side_data_list"]:
                if side_data["side_data_type"] == "Content light level metadata":
                    ctx.maximum_content_light_level = side_data["max_content"]
                    ctx.maximum_frame_average_light_level = side_data["max_average"]
                    print(
                        f"Setting max content light level to {ctx.maximum_content_light_level}"
                    )
                    print(
                        f"Setting max frame average light level to {ctx.maximum_frame_average_light_level}"
                    )
                if side_data["side_data_type"] == "Mastering display metadata":

                    def split_and_divide(spltting) -> float:
                        spl = spltting.split("/")
                        return int(spl[0]) / int(spl[1])

                    red_x = split_and_divide(side_data["red_x"])
                    red_y = split_and_divide(side_data["red_y"])
                    green_x = split_and_divide(side_data["green_x"])
                    green_y = split_and_divide(side_data["green_y"])
                    blue_x = split_and_divide(side_data["blue_x"])
                    blue_y = split_and_divide(side_data["blue_y"])
                    white_point_x = split_and_divide(side_data["white_point_x"])
                    white_point_y = split_and_divide(side_data["white_point_y"])
                    min_luminance = split_and_divide(side_data["min_luminance"])
                    max_luminance = split_and_divide(side_data["max_luminance"])
                    # G(x,y)B(x,y)R(x,y)WP(x,y)L(max,min)
                    ctx.svt_master_display = (
                        f"G({green_x},{green_y})B({blue_x},{blue_y})R({red_x},{red_y})"
                        f"WP({white_point_x},{white_point_y})L({max_luminance},{min_luminance})"
                    )

                    print(f"Setting svt master display to {ctx.svt_master_display}")

            cache_obj = {
                "matrix_coefficients": ctx.matrix_coefficients,
                "color_primaries": ctx.color_primaries,
                "transfer_characteristics": ctx.transfer_characteristics,
                "chroma_sample_position": ctx.chroma_sample_position,
                "maximum_content_light_level": ctx.maximum_content_light_level,
                "maximum_frame_average_light_level": ctx.maximum_frame_average_light_level,
                "svt_master_display": ctx.svt_master_display,
            }

            # save as json
            with open(cache_path, "w") as f:
                f.write(json.dumps(cache_obj))
        else:
            print("Loading HDR10 metadata from cache")
            with open(cache_path) as f:
                cache_obj = json.loads(f.read())
            ctx.matrix_coefficients = cache_obj["matrix_coefficients"]
            ctx.color_primaries = cache_obj["color_primaries"]
            ctx.transfer_characteristics = cache_obj["transfer_characteristics"]
            ctx.chroma_sample_position = cache_obj["chroma_sample_position"]
            ctx.maximum_content_light_level = cache_obj["maximum_content_light_level"]
            ctx.maximum_frame_average_light_level = cache_obj[
                "maximum_frame_average_light_level"
            ]
            ctx.svt_master_display = cache_obj["svt_master_display"]

    return ctx


def setup_rd(ctx: AlabamaContext) -> AlabamaContext:
    if ctx.crf != -1:
        print("Using crf mode")
    else:
        if "auto" in ctx.bitrate_string or "-1" in ctx.bitrate_string:
            if ctx.flag1 and not ctx.crf_based_vmaf_targeting:
                print("Flag1 and auto bitrate are mutually exclusive")
                quit()
            ctx.find_best_bitrate = True
        else:
            if "M" in ctx.bitrate_string or "m" in ctx.bitrate_string:
                ctx.bitrate = ctx.bitrate_string.replace("M", "")
                ctx.bitrate = int(ctx.bitrate) * 1000
            else:
                ctx.bitrate = ctx.bitrate_string.replace("k", "")
                ctx.bitrate = ctx.bitrate_string.replace("K", "")

                try:
                    ctx.bitrate = int(ctx.bitrate_string)
                except ValueError:
                    raise ValueError("Failed to parse bitrate")

        if ctx.flag1 and ctx.bitrate == -1:
            print("Flag1 requires bitrate to be set --bitrate 2M")
            quit()
    return ctx


def compute_resolution_presets(ctx: AlabamaContext) -> AlabamaContext:
    if ctx.resolution_preset != "" and ctx.scale_string == "":
        # 4k 1440p 1080p 768p 720p 540p 480p 360p
        match ctx.resolution_preset:
            case "4k":
                ctx.scale_string = "3840:-2"
            case "1440p":
                ctx.scale_string = "2560:-2"
            case "1080p":
                ctx.scale_string = "1920:-2"
            case "768p":
                ctx.scale_string = "1366:-2"
            case "720p":
                ctx.scale_string = "1280:-2"
            case "540p":
                ctx.scale_string = "960:-2"
            case "480p":
                ctx.scale_string = "854:-2"
            case "432p":
                ctx.scale_string = "768:-2"
            case "360p":
                ctx.scale_string = "640:-2"
            case "240p":
                ctx.scale_string = "480:-2"
            case _:
                raise ValueError(
                    f'Cannot interpret resolution preset "{ctx.resolution_preset}", refer to the help command'
                )
    return ctx


def do_autocrop(ctx: AlabamaContext) -> AlabamaContext:
    if ctx.auto_crop and ctx.crop_string == "":
        cache_path = f"{ctx.temp_folder}cropdetect.cache"
        if not os.path.exists(cache_path):
            start = time.time()
            print("Running cropdetect...")
            output = do_cropdetect(ctx.input_file)
            print(f"Computed crop: {output} in {int(time.time() - start)}s")
            path = PathAlabama(ctx.input_file)
            out_path = PathAlabama(ctx.output_file)

            def gen_prew(ss, i) -> List[str]:
                _p = f'"{out_path.get()}.{i}.cropped.jpg"'
                run_cli(
                    f"{get_binary('ffmpeg')} -v error -y -ss {ss} -i {path.get_safe()} "
                    f"-vf crop={output} -vframes 1 {_p}"
                ).verify()
                p2 = f'"{out_path.get()}.{i}.uncropped.jpg"'
                run_cli(
                    f"{get_binary('ffmpeg')} -v error -y -ss {ss} -i {path.get_safe()} -vframes 1 {p2}"
                )
                return [_p.replace('"', ""), p2.replace('"', "")]

            if not ctx.auto_accept_autocrop:
                print("Creating previews")
                generated_paths = gen_prew(60, 0)
                generated_paths += gen_prew(120, 1)
                print(
                    "Created crop previews in output folder, if you want to use this crop,"
                    " click enter, type anything to abort"
                )

                if input() != "":
                    print("Aborting")
                    for p in generated_paths:
                        if os.path.exists(p):
                            os.remove(p)
                    quit()

                for p in generated_paths:
                    if os.path.exists(p):
                        os.remove(p)

            with open(cache_path, "w") as f:
                f.write(output)
        else:
            print("Loading autocrop from cache")
            with open(cache_path) as f:
                output = f.read()
        ctx.crop_string = output
    return ctx


def run_pipeline(ctx, transformers):
    for transformer in transformers:
        ctx = transformer(ctx)
    return ctx


def setup_context() -> AlabamaContext:
    ctx = AlabamaContext()
    args = parse_args(ctx)

    ctx.output_file = os.path.abspath(args.output)
    ctx.output_folder = os.path.dirname(ctx.output_file) + "/"
    ctx.raw_input_file = os.path.abspath(args.input)
    ctx.encoder = EncodersEnum.from_str(args.encoder)
    ctx.chunk_stats_path = f"{ctx.temp_folder}chunks.log"

    ctx.grain_synth = args.grain
    ctx.log_level = args.log_level
    ctx.dry_run = args.dry_run
    ctx.ssim_db_target = args.ssim_db_target
    ctx.vmaf = args.vmaf_target
    ctx.vbr_perchunk_optimisation = args.vbr_perchunk_optimisation
    ctx.crf_based_vmaf_targeting = args.crf_based_vmaf_targeting
    ctx.use_celery = args.celery
    ctx.flag1 = args.flag1
    ctx.flag2 = args.flag2
    ctx.flag3 = args.flag3
    ctx.override_flags = args.encoder_flag_override
    ctx.speed = args.encoder_speed_override
    ctx.multiprocess_workers = args.multiprocess_workers
    ctx.bitrate_adjust_mode = args.bitrate_adjust_mode
    ctx.bitrate_undershoot = args.undershoot
    ctx.bitrate_overshoot = args.overshoot
    ctx.crf_bitrate_mode = args.auto_crf
    ctx.crf = args.crf
    ctx.hdr = args.hdr
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
    ctx.color_primaries = args.color_primaries
    ctx.transfer_characteristics = args.transfer_characteristics
    ctx.matrix_coefficients = args.matrix_coefficients
    ctx.maximum_content_light_level = args.maximum_content_light_level
    ctx.maximum_frame_average_light_level = args.frame_average_light
    ctx.chroma_sample_position = args.chroma_sample_position
    ctx.video_filters = args.video_filters
    ctx.crf = args.crf
    ctx.auto_crop = args.autocrop
    ctx.bitrate_string = args.bitrate
    ctx.crf_model_weights = args.crf_model_weights
    ctx.vmaf_phone_model = args.vmaf_phone_model
    ctx.vmaf_4k_model = args.vmaf_4k_model
    ctx.auto_accept_autocrop = args.auto_accept_autocrop
    ctx.resolution_preset = args.resolution_preset
    ctx.vmaf_targeting_model = args.vmaf_targeting_model
    ctx.vmaf_probe_count = args.vmaf_probe_count
    ctx.vmaf_reference_display = args.vmaf_reference_display
    ctx.probe_speed_override = args.probe_speed_override

    ctx.find_best_grainsynth = True if ctx.grain_synth == -1 else False

    ctx = run_pipeline(
        ctx,
        [
            setup_paths,
            setup_rd,
            scrape_hdr_metadata,
            do_autocrop,
            compute_resolution_presets,
            setup_video_filters,
        ],
    )

    return ctx


def parse_args(ctx: AlabamaContext):
    parser = argparse.ArgumentParser(
        description="Encode a video using SVT-AV1, and mux it with ffmpeg"
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
        default=ctx.video_filters,
        help="Override the crop, put your vf ffmpeg there, example "
        "scale=-2:1080:flags=lanczos,zscale=t=linear..."
        " make sure ffmpeg on all workers has support for the filters you use",
    )

    parser.add_argument(
        "--bitrate",
        help="Bitrate to use, `auto` for auto bitrate selection",
        type=str,
        default=str(ctx.bitrate),
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
        default=ctx.crf,
        choices=range(0, 63),
    )

    parser.add_argument(
        "--encoder",
        help="What encoder to use",
        type=str,
        default=str(EncodersEnum.SVT_AV1),
        choices=["svt_av1", "x265", "aomenc", "x264", "vpx_9"],
    )

    parser.add_argument(
        "--grain",
        help="Manually give the grainsynth value, 0 to disable, -1 for auto, -2 for auto per scene",
        type=int,
        default=ctx.grain_synth,
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
        default=ctx.hdr,
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
        default=ctx.override_flags,
        help="Override the encoder flags with this string, except paths",
    )

    parser.add_argument(
        "--encoder_speed_override",
        type=int,
        choices=range(0, 8),
        default=ctx.speed,
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
        "--color-primaries",
        type=str,
        default=ctx.color_primaries,
        help="Color primaries",
    )
    parser.add_argument(
        "--transfer-characteristics",
        type=str,
        default=ctx.transfer_characteristics,
        help="Transfer characteristics",
    )
    parser.add_argument(
        "--matrix-coefficients",
        type=str,
        default=ctx.matrix_coefficients,
        help="Matrix coefficients",
    )
    parser.add_argument(
        "--maximum_content_light_level",
        type=str,
        default=ctx.maximum_content_light_level,
        help="Maximum content light level",
    )

    parser.add_argument(
        "--frame-average-light",
        type=str,
        default=ctx.maximum_frame_average_light_level,
        help="Maximum frame average light level",
    )
    parser.add_argument(
        "--chroma-sample-position",
        type=str,
        default=ctx.maximum_frame_average_light_level,
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
        "--vmaf_targeting_model",
        type=str,
        default=ctx.vmaf_targeting_model,
        help="optuna modelless primitive ternary binary",
    )

    parser.add_argument(
        "--vmaf_probe_count",
        type=int,
        default=ctx.vmaf_probe_count,
        help="Number of frames to probe for vmaf, higher is more accurate but slower",
    )

    parser.add_argument(
        "--probe_speed_override",
        type=int,
        default=ctx.speed,
        help="Override the speed for target vmaf probes",
    )

    parser.add_argument(
        "--vmaf_reference_display",
        type=str,
        default=ctx.vmaf_reference_display,
        help="HD FHD UHD ",
    )

    return parser.parse_args()
