import json
import os

from alabamaEncode.cli_executor import run_cli, run_cli_parallel
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
    pipe_ref_path = f"/tmp/{os.path.basename(chunk.path)}.pipe"
    pipe_dist_path = f"/tmp/{os.path.basename(chunk.chunk_path)}.pipe"

    dist_filter = ""

    if comparison_display_resolution is not None:
        comparison_scaling = f"scale={comparison_display_resolution.__str__()}"

        vf = []
        if video_filters != "":
            for filter in video_filters.split(","):
                # if not re.match(r"scale=[0-9-]+:[0-9-]+", filter):
                #     vf.append(filter)
                vf.append(filter)

        vf.append(comparison_scaling)
        video_filters = ",".join(vf)

        dist_filter = f" -vf {comparison_scaling} "

    first_pipe_command = (
        f"ffmpeg -v error -nostdin {chunk.get_ss_ffmpeg_command_pair()} -pix_fmt yuv420p10le  "
        f'-an -sn -strict -1 -vf "{video_filters}" -f yuv4mpegpipe - > {pipe_ref_path}'
    )
    second_pipe_command = (
        f"ffmpeg -v error -nostdin -i {chunk.chunk_path} -pix_fmt yuv420p10le -an -sn "
        f"-strict -1 {dist_filter} -f yuv4mpegpipe - > {pipe_dist_path} "
    )

    if log_path == "":
        log_path = f"/tmp/{os.path.basename(chunk.chunk_path)}.vmaflog"

    # TOsDO: WINDOWS SUPPORT
    run_cli(f'mkfifo "{pipe_ref_path}"')
    run_cli(f'mkfifo "{pipe_dist_path}"')

    # check if both pipes are created
    assert os.path.exists(pipe_ref_path)
    assert os.path.exists(pipe_dist_path)

    vmaf_command = (
        f'vmaf --json --output {log_path} --model {vmaf_options.get_model()} --reference "{pipe_ref_path}" '
        f'--distorted "{pipe_dist_path}" --threads {threads}'
    )

    run_cli_parallel(
        [
            first_pipe_command,
            second_pipe_command,
            vmaf_command,
        ],
        stream_to_stdout=True,
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
