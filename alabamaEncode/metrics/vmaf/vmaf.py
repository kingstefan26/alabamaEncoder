import json
import os
import re

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli, run_cli_parallel
from alabamaEncode.metrics.comp_dis import ComparisonDisplayResolution
from alabamaEncode.metrics.vmaf.options import VmafOptions
from alabamaEncode.metrics.vmaf.result import VmafResult
from alabamaEncode.scene.chunk import ChunkObject


def calc_vmaf(
    chunk: ChunkObject,
    video_filters="",
    comparison_display_resolution: ComparisonDisplayResolution = None,
    threads=1,
    vmaf_options: VmafOptions = None,
    log_path="",
):
    assert vmaf_options is not None

    comparison_display_resolution = (
        vmaf_options.ref
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
                # vf.append(_filter)

        vf.append(comparison_scaling)
        video_filters = ",".join(vf)

        dist_filter = f" -vf {comparison_scaling} "

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

    if log_path == "":
        log_path = f"/tmp/{os.path.basename(chunk.chunk_path)}.vmaflog"

    # TOsDO: WINDOWS SUPPORT
    run_cli(f"mkfifo {pipe_ref_path}")
    run_cli(f"mkfifo {pipe_dist_path}")

    # check if both pipes are created
    assert os.path.exists(pipe_ref_path)
    assert os.path.exists(pipe_dist_path)

    vmaf_command = (
        f'{get_binary("vmaf")} --json --output "{log_path}" --model {vmaf_options.get_model()} '
        f"--reference {pipe_ref_path} "
        f"--distorted {pipe_dist_path} --threads {threads}"
    )

    print(first_pipe_command, second_pipe_command, vmaf_command)

    map(
        lambda x: x.verify(),
        run_cli_parallel(
            [
                first_pipe_command,
                second_pipe_command,
                vmaf_command,
            ]
        ),
    )

    os.remove(pipe_ref_path)
    os.remove(pipe_dist_path)

    log_decoded = json.load(open(log_path))

    os.remove(log_path)

    result = VmafResult(
        pooled_metrics=log_decoded["pooled_metrics"],
        _frames=log_decoded["frames"],
        fps=log_decoded["fps"],
    )
    return result
