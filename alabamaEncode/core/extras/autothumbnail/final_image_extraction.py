import os

from tqdm import tqdm

from alabamaEncode.core.util.bin_utils import (
    check_ffmpeg_libraries,
    check_bin,
    get_binary,
)
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.scene.chunk import ChunkObject


def extract_frames_and_encode(
    best_frames, skip_result_image_optimisation, input_file, output_folder
):
    if skip_result_image_optimisation:
        has_placebo = False
        has_jpegli = False
    else:
        has_placebo = check_ffmpeg_libraries("libplacebo")
        has_jpegli = check_bin("cjpeg")

    os.makedirs(f"{output_folder}/gen_thumbs", exist_ok=True)

    for i, best_frame in tqdm(
        enumerate(best_frames), desc="Saving best frames", total=len(best_frames)
    ):
        chunk = ChunkObject(
            first_frame_index=best_frame,
            last_frame_index=best_frame + 1,
            path=input_file,
        )
        output_path = f'"{output_folder}/gen_thumbs/{i}.png"'
        if has_placebo and has_jpegli:
            command = f"{get_binary('ffmpeg')} -init_hw_device vulkan -y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 -vf 'hwupload,libplacebo=minimum_peak=2:percentile=99.6:tonemapping=spline:colorspace=bt709:color_primaries=bt709:gamut_mode=perceptual:color_trc=bt709:range=tv:gamma=1:format=yuv420p,hwdownload,format=yuv420p' -c:v png -f image2pipe - | {get_binary('cjpeg')} -q 95 -tune-psnr -optimize -progressive > {output_path}"
        elif has_placebo:
            command = f"{get_binary('ffmpeg')} -init_hw_device vulkan -y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 -vf 'hwupload,libplacebo=minimum_peak=2:percentile=99.6:tonemapping=spline:colorspace=bt709:color_primaries=bt709:gamut_mode=perceptual:color_trc=bt709:range=tv:gamma=1:format=yuv420p,hwdownload,format=yuv420p' {output_path}"
        else:
            command = f"{get_binary('ffmpeg')} -y {chunk.get_ss_ffmpeg_command_pair()} -frames:v 1 {output_path}"
        run_cli(command).verify()
