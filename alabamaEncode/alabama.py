import argparse
import os

from tqdm import tqdm

import alabamaEncode.final_touches
from alabamaEncode.encoders.encoder.encoder import AbstractEncoder
from alabamaEncode.encoders.encoderMisc import EncodersEnum, EncoderRateDistribution
from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.utils.binary import doesBinaryExist
from alabamaEncode.utils.ffmpegUtil import do_cropdetect


class AlabamaContext:
    """A class to hold the configuration for the encoder"""

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
    grain_synth: int = -1
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

    chunk_stats_path: str = ""
    find_best_bitrate = False
    find_best_grainsynth = False
    crop_string = ""
    scale_string = ""

    crf_based_vmaf_targeting = True

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

    hdr = False
    color_primaries: int = 1
    transfer_characteristics: int = 1
    matrix_coefficients: int = 1
    maximum_content_light_level: int = 0
    maximum_frame_average_light_level: int = 0
    chroma_sample_position = 0

    def log(self, msg, level=0):
        if self.log_level > 0 and level <= self.log_level:
            tqdm.write(msg)

    def get_encoder(self) -> AbstractEncoder:
        return self.encoder.get_encoder()

    def pre_run_check(self):
        # turn tempfolder into a full path
        self.temp_folder = self.output_folder + "temp/"
        if not os.path.exists(self.temp_folder):
            os.makedirs(self.temp_folder)

        self.input_file = self.temp_folder + "temp.mkv"

        if not os.path.exists(self.raw_input_file):
            print(f"Input file {self.raw_input_file} does not exist")
            quit()

        # symlink input file to temp folder
        if not os.path.exists(self.input_file):
            os.system(f'ln -s "{self.raw_input_file}" "{self.input_file}"')
            if not os.path.exists(self.input_file):
                print(f"Failed to symlink input file to {self.input_file}")
                quit()

    def update(self, **kwargs):
        """
        Update the config with new values, with type checking
        """
        if "temp_folder" in kwargs:
            self.temp_folder = kwargs.get("temp_folder")
            if not os.path.isdir(self.temp_folder):
                raise Exception("FATAL: temp_folder must be a valid directory")
        if "bitrate" in kwargs:
            self.bitrate = kwargs.get("bitrate")
            if not isinstance(self.bitrate, int):
                raise Exception("FATAL: bitrate must be an int")
        if "crf" in kwargs:
            self.crf = kwargs.get("crf")
            if not isinstance(self.crf, int):
                raise Exception("FATAL: crf must be an int")
        if "passes" in kwargs:
            self.passes = kwargs.get("passes")
            if not isinstance(self.passes, int):
                raise Exception("FATAL: passes must be an int")
        if "video_filters" in kwargs:
            self.video_filters = kwargs.get("video_filters")
            if not isinstance(self.video_filters, str):
                raise Exception("FATAL: video_filters must be a str")
        if "speed" in kwargs:
            self.speed = kwargs.get("speed")
            if not isinstance(self.speed, int):
                raise Exception("FATAL: speed must be an int")
        if "threads" in kwargs:
            self.threads = kwargs.get("threads")
            if not isinstance(self.threads, int):
                raise Exception("FATAL: threads must be an int")
        if "rate_distribution" in kwargs:
            self.rate_distribution = kwargs.get("rate_distribution")
            if not isinstance(self.rate_distribution, EncoderRateDistribution):
                raise Exception("FATAL: rate_distribution must be an RateDistribution")
        if "qm_enabled" in kwargs:
            self.qm_enabled = kwargs.get("qm_enabled")
            if not isinstance(self.qm_enabled, bool):
                raise Exception("FATAL: qm_enabled must be an bool")
        if "qm_min" in kwargs:
            self.qm_min = kwargs.get("qm_min")
            if not isinstance(self.qm_min, int):
                raise Exception("FATAL: qm_min must be an int")
        if "qm_max" in kwargs:
            self.qm_max = kwargs.get("qm_max")
            if not isinstance(self.qm_max, int):
                raise Exception("FATAL: qm_max must be an int")


def setup_context() -> AlabamaContext:
    ctx = AlabamaContext()
    args = parse_args(ctx)

    ctx.output_file = os.path.abspath(args.output)
    ctx.output_folder = os.path.dirname(ctx.output_file) + "/"
    ctx.raw_input_file = os.path.abspath(args.input)
    ctx.encoder = EncodersEnum.from_str(args.encoder)
    ctx.chunk_stats_path = f"{ctx.temp_folder}chunks.log"

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
    ctx.generate_previews = alabamaEncode.final_touches.generate_previews
    ctx.encode_audio = args.encode_audio
    ctx.sub_file = args.sub_file
    ctx.color_primaries = args.color_primaries
    ctx.transfer_characteristics = args.transfer_characteristics
    ctx.matrix_coefficients = args.matrix_coefficients
    ctx.maximum_content_light_level = args.maximum_content_light_level
    ctx.maximum_frame_average_light_level = args.frame_average_light
    ctx.chroma_sample_position = args.chroma_sample_position
    ctx.grain_synth = args.grain
    ctx.video_filters = args.video_filters

    ctx.pre_run_check()

    if ctx.crf != -1:
        print("Using crf mode")
        ctx.crf = args.crf
    if ctx.flag1 and ctx.bitrate == -1:
        print("Flag1 requires bitrate to be set --bitrate 2M")
        quit()
    if (
        "auto" in args.bitrate
        or "-1" in args.bitrate
        and ctx.flag1
        and not ctx.crf_based_vmaf_targeting
    ):
        print("Flag1 and auto bitrate are mutually exclusive")
        quit()

    if "auto" in args.bitrate or "-1" in args.bitrate:
        ctx.find_best_bitrate = True
    else:
        if "M" in args.bitrate or "m" in args.bitrate:
            ctx.bitrate = args.bitrate.replace("M", "")
            ctx.bitrate = int(ctx.bitrate) * 1000
        else:
            ctx.bitrate = args.bitrate.replace("k", "")
            ctx.bitrate = args.bitrate.replace("K", "")

            try:
                ctx.bitrate = int(args.bitrate)
            except ValueError:
                raise ValueError("Failed to parse bitrate")

    ctx.find_best_grainsynth = True if args.grain == -1 else False
    if ctx.find_best_grainsynth and not doesBinaryExist("butteraugli"):
        print("Autograin requires butteraugli in path, please install it")
        quit()

    # make --video_filters mutually exclusive with --hdr --crop_string --scale_string
    if ctx.video_filters != "" and (
        ctx.hdr or ctx.video_filters != "" or ctx.scale_string != ""
    ):
        print(
            "--video_filters is mutually exclusive with --hdr, --crop_string, and --scale_string"
        )
        quit()

    if ctx.video_filters == "":
        if args.autocrop:
            output = do_cropdetect(ChunkObject(path=ctx.input_file))
            output.replace("crop=", "")
            if output != "":
                ctx.video_filters = output

        final = ""

        if ctx.crop_string != "":
            final += f"crop={ctx.crop_string}"

        if ctx.scale_string != "":
            if final != "" and final[-1] != ",":
                final += ","
            final += f"scale={ctx.scale_string}:flags=lanczos"

        if ctx.hdr == False and Ffmpeg.is_hdr(PathAlabama(ctx.input_file)):
            if final != "" and final[-1] != ",":
                final += ","
            final += Ffmpeg.get_tonemap_vf()

        ctx.video_filters = final

    if ctx.encoder == EncodersEnum.X265 and ctx.crf_bitrate_mode == False:
        print("x265 only supports auto crf, set `--auto_crf true`")
        quit()

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
        action="store_true",
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
        choices=["svt_av1", "x265", "aomenc", "x264"],
    )

    parser.add_argument(
        "--grain",
        help="Manually give the grainsynth value, 0 to disable, -1 for auto",
        type=int,
        default=ctx.grain_synth,
        choices=range(-1, 63),
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
        action="store_true",
        default=ctx.crf_based_vmaf_targeting,
    )

    parser.add_argument(
        "--auto_crf",
        help="Find a crf that hits target vmaf, calculate a peak bitrate cap, and encode using that",
        action="store_true",
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
        action="store_true",
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

    return parser.parse_args()
