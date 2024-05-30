import subprocess

from alabamaEncode.core.util.abort_controler import AbortControler
from alabamaEncode.core.util.yuv import Reader
from alabamaEncode.scene.chunk import ChunkObject


def get_yuv_frame_stream(chunk: ChunkObject, frame_callback, vf: str= "", abort_controler: AbortControler = None):
    command = chunk.create_chunk_ffmpeg_pipe_command(video_filters=vf, bit_depth=8)

    ffmpeg_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    yuv_reader = Reader(frame_callback)

    while ffmpeg_process.poll() is None:
        if abort_controler:
            if abort_controler.aborted:
                break
        data = ffmpeg_process.stdout.read(1024 * 1024)
        if data:
            yuv_reader.decode(data)
