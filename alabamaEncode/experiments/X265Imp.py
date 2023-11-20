"""
Testing the x265 implementation of the encoder interface.
"""

import os

from alabamaEncode.encoder.impl.X265 import EncoderX265
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.experiments.util.ExperimentUtil import get_test_files
from alabamaEncode.scene.chunk import ChunkObject

if __name__ == "__main__":
    paths = get_test_files()[:3]

    for path in paths:
        print(f"\n\n## Doing: {path}")

        test_env = "./tstCRF" + path.split("/")[-1].split(".")[0] + "/"
        if not os.path.exists(test_env):
            os.mkdir(test_env)

        x265 = EncoderX265()

        x265.update(
            rate_distribution=EncoderRateDistribution.CQ,
            crf=18,
            passes=1,
            chunk=ChunkObject(path=path),
            current_scene_index=0,
            threads=12,
            speed=0,
            output_path=f"{test_env}_owo.mkv",
        )

        print("command: ", x265.get_encode_commands())
        stats = x265.run(override_if_exists=False, calculate_vmaf=True)
        stats.time_encoding = round(stats.time_encoding, 2)

        print(
            f" {stats.time_encoding}s |"
            f" {stats.bitrate} "
            f"| {round(stats.vmaf, 2)} | "
        )
