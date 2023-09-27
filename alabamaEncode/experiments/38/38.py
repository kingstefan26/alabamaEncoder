"""
Testing the x265 implementation of the encoder interface.
"""

import os

from alabamaEncode.encoders.encoderImpl.X265 import AbstractEncoderX265

from alabamaEncode.encoders.RateDiss import RateDistribution
from alabamaEncode.sceneSplit.ChunkOffset import ChunkObject

if __name__ == "__main__":
    paths = [
        "/mnt/data/liveAction_normal.mp4",
        "/mnt/data/liveAction_highMotion.mkv",
        "/mnt/data/liveaction_bright.mkv",
    ]

    for path in paths:
        print(f"\n\n## Doing: {path}")
        chunk = ChunkObject(path=path, first_frame_index=0, last_frame_index=200)

        test_env = "./tstCRF" + path.split("/")[-1].split(".")[0] + "/"
        # shutil.rmtree(test_env, ignore_errors=True)
        if not os.path.exists(test_env):
            os.mkdir(test_env)

        crope_stringe = ""

        if "liveAction_normal" in path:
            # clip is 4k but we only want to encode 1080p, also map from hdr
            crope_stringe = "crop=3808:1744:28:208,scale=-2:1080:flags=lanczos,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=reinhard:desat=0,zscale=t=bt709:m=bt709:r=tv"
        elif "liveAction_highMotion" in path:
            # crop black borders
            crope_stringe = "crop=1920:800:0:140"
        elif "liveAction_4k" in path:
            # the same clip as liveAction_normal but in we dont scale down to 1080p
            crope_stringe = "crop=3808:1744:28:208,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=reinhard:desat=0,zscale=t=bt709:m=bt709:r=tv"
        elif "liveaction_bright" in path:
            crope_stringe = "crop=1920:960:0:60"

        x265 = AbstractEncoderX265()

        x265.update(
            rate_distribution=RateDistribution.CQ,
            crf=18,
            passes=1,
            chunk=chunk,
            current_scene_index=0,
            threads=12,
            video_filters=crope_stringe,
            speed=0,
            output_path=f"{test_env}_owo.mkv",
        )

        print("command: ", x265.get_encode_commands())
        # quit()
        stats = x265.run(override_if_exists=False, calculate_vmaf=True)
        stats.time_encoding = round(stats.time_encoding, 2)

        print(
            f" {stats.time_encoding}s |"
            f" {stats.bitrate} "
            f"| {round(stats.vmaf, 2)} | "
        )
