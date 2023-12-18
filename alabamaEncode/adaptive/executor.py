import json
import os
import time

from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.core.timer import Timer
from alabamaEncode.encoder.encoder_enum import EncodersEnum
from alabamaEncode.parallelEncoding.command import BaseCommandObject
from alabamaEncode.scene.chunk import ChunkObject


class AdaptiveCommand(BaseCommandObject):
    """
    Class that gets the ideal bitrate and encodes the final chunk
    """

    ctx: AlabamaContext
    chunk: ChunkObject

    pin_to_core = -1

    def __init__(self, ctx: AlabamaContext, chunk: ChunkObject):
        super().__init__()
        self.ctx = ctx
        self.chunk = chunk
        self.encoded_a_frame_callback: callable = None

    # how long (seconds) before we time out the final encoding
    # currently set to 30 minutes
    final_encode_timeout = 1800

    run_on_celery = False

    def supports_encoded_a_frame_callback(self):
        return self.ctx.prototype_encoder.get_enum() == EncodersEnum.SVT_AV1

    def run(self):
        total_start = time.time()

        # using it with a statement with MessageWriter
        timeing = Timer()

        timeing.start("analyze_step")

        enc = self.ctx.get_encoder()
        enc.pin_to_core = self.pin_to_core
        enc.chunk = self.chunk
        for step in self.ctx.chunk_analyze_chain:
            timeing.start(f"analyze_step_{step.__class__.__name__}")
            enc = step.run(self.ctx, self.chunk, enc)
            timeing.stop(f"analyze_step_{step.__class__.__name__}")

        rate_search_time = timeing.stop("analyze_step")

        enc.running_on_celery = self.run_on_celery

        if self.ctx.dry_run:
            print(f"dry run chunk: {self.chunk.chunk_index}")
            print(self.ctx.chunk_encode_class.dry_run(enc, self.chunk))
            return

        timeing.start("final_step")

        try:
            final_stats = self.ctx.chunk_encode_class.run(
                enc,
                chunk=self.chunk,
                ctx=self.ctx,
                encoded_a_frame=self.encoded_a_frame_callback,
            )
        except Exception as e:
            self.ctx.log(f"final encoding failed: {e}", level=1)
            if os.path.exists(self.chunk.chunk_path):
                os.remove(self.chunk.chunk_path)
            return

        timeing.stop("final_step")
        timeing.finish()

        # round to two places
        total_fps = round(self.chunk.get_frame_count() / (time.time() - total_start), 2)
        final_stats.total_fps = total_fps
        final_stats.chunk_index = self.chunk.chunk_index
        final_stats.rate_search_time = rate_search_time
        self.ctx.log(
            f"[{self.chunk.chunk_index}] final stats:"
            f" vmaf={final_stats.vmaf} "
            f" time={int(final_stats.time_encoding)}s "
            f" bitrate={final_stats.bitrate}k"
            f" chunk_length={round(self.chunk.get_lenght(), 2)}s"
            f" total_fps={total_fps}"
        )
        # save the stats to [temp_folder]/chunks.log
        with open(f"{self.ctx.temp_folder}/chunks.log", "a") as f:
            f.write(json.dumps(final_stats.__dict__()) + "\n")

        return self.pin_to_core
