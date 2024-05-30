import os

from alabamaEncode.core.util.bin_utils import register_bin
from alabamaEncode.encoder.impl.X264 import EncoderX264
from alabamaEncode.experiments.util.ExperimentUtil import get_test_files
from alabamaEncode.scene.chunk import ChunkObject

if __name__ == "__main__":
    test_env = "./tst_streaming_output/"
    test_env = os.path.abspath(test_env)
    if not os.path.exists(test_env):
        os.mkdir(test_env)
    register_bin("SvtAv1EncApp", "/home/kokoniara/.local/opt/SvtAv1EncApp")
    enc = EncoderX264()
    enc.chunk = ChunkObject(path=get_test_files()[0])
    enc.output_path = os.path.join(test_env, "output.mkv")
    enc.speed = 12
    enc.crf = 30
    enc.passes = 1

    enc.run(
        on_frame_encoded=lambda frame, bitrate, fps: print(f"{frame} {bitrate} {fps}")
    )
