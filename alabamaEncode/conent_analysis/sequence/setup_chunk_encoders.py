import os
import random

from alabamaEncode.conent_analysis.opinionated_vmaf import get_vmaf_list
from alabamaEncode.core.chunk_encoder import ChunkEncoder
from alabamaEncode.scene.annel import annealing


def setup_chunk_encoders(ctx, sequence):
    def is_chunk_done(_chunk):
        if ctx.multi_res_pipeline:
            enc = ctx.get_encoder()
            vmafs = get_vmaf_list(enc.get_codec())

            for vmaf in vmafs:
                output_path = (
                    f"{ctx.temp_folder}/"
                    f"{_chunk.chunk_index}_{vmaf}.{enc.get_chunk_file_extension()}"
                )
                if not os.path.exists(output_path):
                    return False

            return True
        else:
            return _chunk.is_done(kv=ctx.get_kv())

    for chunk in sequence.chunks:
        if not is_chunk_done(chunk):
            ctx.chunk_jobs.append(ChunkEncoder(ctx, chunk))
        else:
            ctx.last_session_encoded_frames += chunk.get_frame_count()
            ctx.last_session_size_kb += chunk.get_filesize() / 1000

    if len(ctx.chunk_jobs) > 1:
        threads = os.cpu_count()
        if len(ctx.chunk_jobs) < threads:
            ctx.prototype_encoder.threads = int(threads / len(ctx.chunk_jobs))

    if len(ctx.chunk_jobs) > 2:
        if ctx.throughput_scaling and ctx.chunk_order != "even":
            print("Forcing chunk order to even")
            ctx.chunk_order = "even"

        match ctx.chunk_order:
            case "random":
                random.shuffle(ctx.chunk_jobs)
            case "length_asc":
                ctx.chunk_jobs.sort(key=lambda x: x.chunk.length)
            case "length_desc":
                ctx.chunk_jobs.sort(key=lambda x: x.chunk.length, reverse=True)
            case "even":
                ctx.chunk_jobs = annealing(ctx.chunk_jobs, 1000)
            case "reverse":
                ctx.chunk_jobs.reverse()
            case "sequential":
                pass
            case _:
                raise ValueError(f"Invalid chunk order: {ctx.chunk_order}")

    return ctx
