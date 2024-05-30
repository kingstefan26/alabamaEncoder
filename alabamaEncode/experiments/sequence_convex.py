import os

from alabamaEncode.conent_analysis.chunk.analyze_steps.target_vmaf import TargetVmaf
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.util.bin_utils import register_bin
from alabamaEncode.encoder.impl.X264 import EncoderX264
from alabamaEncode.metrics.comparison_display import ComparisonDisplayResolution
from alabamaEncode.metrics.impl.vmaf import VmafOptions
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.scene_detection import scene_detect
from alabamaEncode.scene.sequence import ChunkSequence

if __name__ == "__main__":
    env = "./seq_convexhull"
    env = os.path.abspath(env)
    if not os.path.exists(env):
        os.mkdir(env)

    scenes: ChunkSequence = scene_detect(
        input_file="/home/kokoniara/ep3_halo_test.mkv",
        max_scene_length=10,
        cache_file_path=f"{env}/scenes_skinny.pt",
    )

    scenes.setup_paths(env, ".mkv")

    register_bin("SvtAv1EncApp", "/home/kokoniara/.local/opt/SvtAv1EncApp")
    ref_display = ComparisonDisplayResolution.FHD
    resolutions = [
        "1920:-2",
        "1366:-2",
        "1280:-2",
        "960:-2",
        # "854:-2",
        # "768:-2",
        # "640:-2",
        # "480:-2",
    ]
    vmaf_targets = [45, 55, 62, 68, 81, 87, 90, 93, 95, 97]
    ctx = AlabamaContext()
    ctx.vmaf_reference_display = "FHD"
    ctx.temp_folder = env

    enc = EncoderX264()
    enc.speed = 2

    for scene in scenes.chunks:
        for res in resolutions:
            ctx.vmaf = 95
            enc.video_filters = f"crop=3840:1920:0:120,scale={res}"
            scene.chunk_path = os.path.join(env, f"{res.split(':')[0]}p_{ctx.vmaf}.mkv")
            enc.chunk = scene
            ctx.probe_speed = enc.speed
            tar = TargetVmaf()
            tar.run(chunk=scene, ctx=ctx, enc=enc)
            print(f"res: {res}, target 95, computed crf: {enc.crf}")

            stats = enc.run(
                metric_to_calculate=Metric.VMAF,
                metric_params=VmafOptions(ref=ref_display),
            )
            print(
                f"target 95, res: {res}, final vmaf: {stats.vmaf} crf: {enc.crf} bitrate: {stats.bitrate}"
            )
