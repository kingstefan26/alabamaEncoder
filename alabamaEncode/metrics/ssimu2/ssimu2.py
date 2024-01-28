import os
import re

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli, run_cli_parallel
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.metric_exeption import Ssimu2Exception
from alabamaEncode.metrics.ssimu2.ssimu2_options import Ssimu2Options
from alabamaEncode.scene.chunk import ChunkObject


def calc_ssimu2(
    chunk: ChunkObject,
    video_filters="",
    comparison_display_resolution: ComparisonDisplayResolution = None,
    threads=1,
    ssimu2_options: Ssimu2Options = None,
):
    assert ssimu2_options is not None

    comparison_display_resolution = (
        ssimu2_options.ref
        if comparison_display_resolution is None
        else comparison_display_resolution
    )

    assert os.path.exists(chunk.path)
    assert os.path.exists(chunk.chunk_path)

    random_bit = os.urandom(16).hex()
    pipe_ref_path = f"/tmp/{os.path.basename(chunk.path)}_{random_bit}.pipe"
    pipe_dist_path = f"/tmp/{os.path.basename(chunk.chunk_path)}_{random_bit}.pipe"

    dist_filter = ""

    if comparison_display_resolution is not None:
        comparison_scaling = f"scale={comparison_display_resolution.__str__()}"

        vf = []
        if video_filters != "":
            for _filter in video_filters.split(","):
                if not re.match(r"scale=[0-9-]+:[0-9-]+", _filter):
                    vf.append(_filter)

        vf.append(comparison_scaling)
        video_filters = ",".join(vf)

        dist_filter = f" -vf {comparison_scaling} "

    if ssimu2_options.denoise_reference:
        # before scaling use the `vaguedenoiser` filter
        vf = video_filters.split(",")
        # add to the front of a list
        vf.insert(0, "vaguedenoiser")
        video_filters = ",".join(vf)

    video_filters = ",".join([f for f in video_filters.split(",") if f != ""])

    if video_filters != "":
        video_filters = f" -vf {video_filters} "

    first_pipe_command = (
        f"{get_binary('ffmpeg')} -v error -nostdin -hwaccel auto {chunk.get_ss_ffmpeg_command_pair()}"
        f" -pix_fmt yuv420p10le -an -sn -strict -1 {video_filters} -f yuv4mpegpipe - > {pipe_ref_path}"
    )
    second_pipe_command = (
        f'{get_binary("ffmpeg")} -v error -nostdin -filmgrain 0 -hwaccel auto -i "{chunk.chunk_path}" '
        f"-pix_fmt yuv420p10le -an -sn -strict -1 {dist_filter} -f yuv4mpegpipe - > {pipe_dist_path}"
    )

    # TODO: WINDOWS SUPPORT
    run_cli(f"mkfifo {pipe_ref_path}")
    run_cli(f"mkfifo {pipe_dist_path}")

    # check if both pipes are created
    assert os.path.exists(pipe_ref_path)
    assert os.path.exists(pipe_dist_path)

    main_command = (
        f"{get_binary('ssimulacra2_rs')} video {pipe_ref_path} {pipe_dist_path} "
    )

    print(first_pipe_command)
    print(second_pipe_command)
    print(main_command)
    return None

    cli_results = run_cli_parallel(
        [
            first_pipe_command,
            second_pipe_command,
            main_command,
        ]
    )

    for c in cli_results:
        try:
            c.verify()
        except RuntimeError as e:
            raise Ssimu2Exception(
                f"Could not run ssimu2 command: {e}, {[c.output for c in cli_results]}"
            )

    print(cli_results[2].output)
