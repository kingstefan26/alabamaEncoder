"""
Testing svtav1 speed 2v3v4 and which one is the best tradeoff
"""
import os

from alabamaEncode.encoders.encoder.impl.Svtenc import AbstractEncoderSvtenc
from alabamaEncode.encoders.encoderMisc import EncoderRateDistribution
from alabamaEncode.experiments.util.ExperimentUtil import get_test_files
from alabamaEncode.scene.chunk import ChunkObject

if __name__ == "__main__":
    paths = get_test_files()[:6]


    for path in paths:
        print(f"\n\nDoing: {path}")
        chunk = ChunkObject(path=path, first_frame_index=0, last_frame_index=200)

        crope_stringe = ""

        svtenc = AbstractEncoderSvtenc()

        svtenc.update()
        svtenc.svt_chroma_thing = 0
        svtenc.keyint = 999
        svtenc.svt_bias_pct = 50
        svtenc.svt_open_gop = False

        test_env = "./tstVBR" + path.split("/")[-1].split(".")[0] + "/"
        # shutil.rmtree(test_env, ignore_errors=True)
        if not os.path.exists(test_env):
            os.mkdir(test_env)

        svtenc.update(
            rate_distribution=EncoderRateDistribution.VBR,
            bitrate=1500,
            passes=3,
            chunk=chunk,
            current_scene_index=0,
            threads=12,
            video_filters=crope_stringe,
            grain_synth=3,
        )

        if "liveAction_normal" in path:
            svtenc.update(bitrate=1000)
        elif "liveAction_highMotion" in path:
            svtenc.update(bitrate=2000)
        elif "Animation" in path:
            svtenc.update(bitrate=1500)
        elif "stopmotion" in path:
            svtenc.update(bitrate=3000)
        elif "liveAction_4k" in path:
            svtenc.update(bitrate=4000)
        elif "liveaction_bright" in path:
            svtenc.update(bitrate=1000)

        svtenc.update(rate_distribution=EncoderRateDistribution.VBR, passes=3)

        print(
            f"| _Vbr {svtenc.bitrate}_ |  time taken  | kpbs | vmaf  | BD Change % | time Change % |\n"
            "|----------|:------:|:----:|:-----:|:-----------:|:---:|"
        )
        four_dbrate = -1
        four_time = -1
        for speed in [4, 3, 2]:
            print(f"\nRunning speed {speed}")
            svtenc.update(output_path=f"{test_env}speed{speed}.ivf", speed=speed)
            print(svtenc.get_encode_commands())
            quit()
            stats = svtenc.run(override_if_exists=False, calculate_vmaf=True)

            curr_db_rate = stats.size / stats.vmaf
            if speed == 4:
                four_time = stats.time_encoding
                four_dbrate = curr_db_rate

            change_from_zero = (curr_db_rate - four_dbrate) / four_dbrate * 100
            change_from_zero_time = (stats.time_encoding - four_time) / four_time * 100
            print(
                f"| {speed} |"
                f" {stats.time_encoding}s |"
                f" {stats.bitrate} "
                f"| {stats.vmaf} | "
                f" {change_from_zero}% |"
                f" {change_from_zero_time}% |"
            )
