import json
import os

from tqdm import tqdm

from alabamaEncode.conent_analysis.chunk.final_encode_steps.dynamic_target_vmaf import (
    DynamicTargetVmaf,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.util.timer import Timer
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.parallel_execution.command import BaseCommandObject
from alabamaEncode.scene.chunk import ChunkObject


class ChunkEncoder(BaseCommandObject):
    """
    Take a chunk, run it through the pipeline and encode it
    """

    def __init__(self, ctx: AlabamaContext, chunk: ChunkObject):
        super().__init__()
        self.ctx = ctx
        self.chunk = chunk
        self.encoded_a_frame_callback: callable = None
        self.pin_to_core = -1
        # how long (seconds) before we time out the final encoding
        # currently set to 30 minutes
        self.final_encode_timeout = 1800
        self.run_on_celery = False

    def supports_encoded_a_frame_callback(self):
        return isinstance(self.ctx.prototype_encoder, EncoderSvt) and not isinstance(
            self.ctx.chunk_encode_class, DynamicTargetVmaf
        )

    def run(self) -> [int, EncodeStats]:
        timeing = Timer()

        timeing.start("chunk")
        try:
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
            chunk_stats = self.ctx.chunk_encode_class.run(
                enc,
                chunk=self.chunk,
                ctx=self.ctx,
                encoded_a_frame=self.encoded_a_frame_callback,
            )
            timeing.stop("final_step")
        except Exception as e:
            tqdm.write(f"{self.chunk.log_prefix()}encoding failed: {e}")
            if os.path.exists(self.chunk.chunk_path):
                os.remove(self.chunk.chunk_path)
            return

        valid = self.chunk.verify_integrity(
            length_of_sequence=self.ctx.total_chunks, quiet=True
        )
        self.ctx.get_kv().set("chunk_integrity", self.chunk.chunk_index, not valid)

        timeing.stop("chunk")
        timing_stats = timeing.finish()

        if chunk_stats is None:
            return self.pin_to_core, None

        chunk_stats.total_fps = round(
            self.chunk.get_frame_count() / (timing_stats["chunk"]), 2
        )
        chunk_stats.chunk_index = self.chunk.chunk_index
        chunk_stats.rate_search_time = rate_search_time

        with open(f"{self.ctx.temp_folder}/chunks.log", "a") as f:
            f.write(json.dumps(chunk_stats.__dict__()) + "\n")

        self.ctx.get_kv().set("chunk_timing", self.chunk.chunk_index, timing_stats)

        return self.pin_to_core, chunk_stats.__dict__()
